#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  crimson_forge/binary.py
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the  nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import collections
import collections.abc

import crimson_forge.block as block
import crimson_forge.ir as ir
import crimson_forge.utilities as utilities

class Binary(utilities.Base):
	def __init__(self, blob, arch, base=0x1000):
		super(Binary, self).__init__(blob, arch, base)
		self.cs_instructions.update((ins.address, ins) for ins in self._disassemble(blob))
		self.blocks = collections.OrderedDict()
		self._block_from_irsb(self.__vex_lift(blob))
		self.blocks = collections.OrderedDict((addr, self.blocks[addr]) for addr in sorted(self.blocks.keys()))
		for block in self.blocks.values():
			self.vex_instructions.update(block.vex_instructions.items())

	@property
	def base(self):
		return self.address

	def _disassemble(self, blob):
		yield from self.arch.capstone.disasm(blob, self.base)

	def _block_from_irsb(self, irsb, parent=None):
		offset = irsb.addr - self.base
		blob = self.bytes[offset:offset + irsb.size]
		cs_instructions = collections.OrderedDict()
		cs_instructions.update((addr, self.cs_instructions[addr]) for addr in irsb.instruction_addresses)
		bblock = block.BasicBlock.from_irsb(blob, cs_instructions, irsb)
		if parent is not None:
			parent.connect_to(bblock)
		self.blocks[bblock.address] = bblock
		# search blocks to see if any instructions overlap with an existing block and if so
		# split and propagate relationships
		for address in tuple(bblock.cs_instructions.keys())[1:]:
			original_bblock = self.blocks.pop(address, None)
			if original_bblock is None:
				continue
			sub_bblock = bblock.split(address)
			sub_bblock.parents.update(original_bblock.parents)
			sub_bblock.children.update(original_bblock.children)
			self.blocks[sub_bblock.address] = sub_bblock
			break
		# we split the original block, so irsb is no longer an accurate representation and
		# so we skip this step since the relations are already connected
		else:
			for address, jumpkind in irsb.constant_jump_targets_and_jumpkinds.items():
				if jumpkind not in ('Ijk_Boring', 'Ijk_Call'):
					continue
				self.__block_from_irsb_next(bblock, address)
			if irsb.jumpkind == 'Ijk_Call':
				self.__block_from_irsb_next(bblock, bblock.address + len(bblock.bytes))
		return bblock

	def __block_from_irsb_next(self, bblock, address):
		# search through existing blocks to find a pre-existing one that
		# contains the jump target and split it
		for jmp_bblock in self.blocks.values():
			if address not in jmp_bblock.cs_instructions:
				continue
			connect_to_self = jmp_bblock is bblock
			if jmp_bblock.address != address:
				jmp_bblock = jmp_bblock.split(address)
				self.blocks[jmp_bblock.address] = jmp_bblock
			if connect_to_self:
				jmp_bblock.connect_to(jmp_bblock)
			bblock.connect_to(jmp_bblock)
			break
		# if no block is found, build a new one from the blob (if there is data left)
		else:
			blob = self.bytes[address - self.base:]
			if blob:
				self._block_from_irsb(self.__vex_lift(blob, address), parent=bblock)

	def __vex_lift(self, blob, base=None):
		base = self.base if base is None else base
		return ir.lift(blob, base, self.arch)

	@classmethod
	def from_source(cls, source, arch, base=0x1000):
		blob, _ = arch.keystone.asm(utilities.remove_comments(source))
		return cls(bytes(blob), arch, base=base)

	def shuffle(self):
		blocks = [block.shuffle() for block in self.blocks.values()]
		blob = b''.join(block.bytes for block in blocks)
		return self.__class__(blob, self.arch, self.base)
