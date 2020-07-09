#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  crimson_forge/utilities.py
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
import enum
import logging
import os
import re
import traceback

import archinfo
import termcolor

LEVEL_COLORS = {
	logging.DEBUG: ('cyan',),
	logging.INFO: ('white',),
	logging.WARNING: ('yellow',),
	logging.ERROR: ('red',),
	logging.CRITICAL: ('white', 'on_red')
}

class _Architectures(collections.abc.Mapping):
	aliases = {
		'x64': 'amd64',
		'x86-64': 'amd64'
	}
	__values = collections.OrderedDict((
		('amd64', archinfo.ArchAMD64()),
		('x86',  archinfo.ArchX86())
	))
	def __getitem__(self, item):
		item = item.lower()
		item = self.aliases.get(item, item)
		return self.__values[item]

	def __iter__(self):
		return iter(self.__values)

	def __len__(self):
		return len(self.__values)

architectures = _Architectures()

print_colors = True

def print_error(message):
	"""
	Print an error message to the console.

	:param str message: The message to print
	"""
	prefix = '[-] '
	if print_colors:
		prefix = termcolor.colored(prefix, 'red', attrs=['bold'])
	print(prefix + message)

def print_good(message):
	"""
	Print a good message to the console.

	:param str message: The message to print
	"""
	prefix = '[+] '
	if print_colors:
		prefix = termcolor.colored(prefix, 'green', attrs=['bold'])
	print(prefix + message)

def print_status(message):
	"""
	Print a status message to the console.

	:param str message: The message to print
	"""
	prefix = '[*] '
	if print_colors:
		prefix = termcolor.colored(prefix, 'blue', attrs=['bold'])
	print(prefix + message)

def print_warning(message):
	"""
	Print a warning message to the console.

	:param str message: The message to print
	"""
	prefix = '[!] '
	if print_colors:
		prefix = termcolor.colored(prefix, 'yellow', attrs=['bold'])
	print(prefix + message)

class ColoredLogFormatter(logging.Formatter):
	"""
	A formatting class suitable for use with the :py:mod:`logging` module which
	colorizes the names of log levels.
	"""
	def format(self, record):
		orig_levelname = None
		if record.levelno in LEVEL_COLORS:
			orig_levelname = record.levelname
			record.levelname = termcolor.colored("{0:<8}".format(record.levelname), *LEVEL_COLORS[record.levelno], attrs=['bold'])
		value = super(ColoredLogFormatter, self).format(record)
		record.exc_text = None
		if orig_levelname is not None:
			record.levelname = orig_levelname
		return value

	@staticmethod
	def formatException(exc_info):
		tb_lines = traceback.format_exception(*exc_info)
		tb_lines[0] = termcolor.colored(tb_lines[0], 'red', attrs=['bold'])
		for line_no, line in enumerate(tb_lines[1:], 1):
			search = re.search(r'File \"([^"]+)", line ([\d,]+), in', line)
			if search:
				new_line = line[:search.start(1)]
				new_line += termcolor.colored(search.group(1), 'yellow', attrs=['underline'])
				new_line += line[search.end(1):search.start(2)]
				new_line += termcolor.colored(search.group(2), 'white', attrs=['bold'])
				new_line += line[search.end(2):]
				tb_lines[line_no] = new_line
		line = tb_lines[-1]
		if line.find(':'):
			idx = line.find(':')
			line = termcolor.colored(line[:idx], 'red', attrs=['bold']) + line[idx:]
		if line.endswith(os.linesep):
			line = line[:-len(os.linesep)]
		tb_lines[-1] = line
		return ''.join(tb_lines)

_DataFormatSpec = collections.namedtuple('_DataFormatSpec', ('value', 'extension'))
@enum.unique
class DataFormat(enum.Enum):
	def __new__(cls, value, extension, **kwargs):
		obj = object.__new__(cls)
		obj._value_ = value
		obj.extension = extension
		return obj
	PE_EXE = _DataFormatSpec('pe:exe', 'exe')
	#PE_EXE_DLL = _DataFormatSpec('pe:exe:dll', 'dll')
	PE_EXE_SVC = _DataFormatSpec('pe:exe:svc', 'svc.exe')
	RAW = _DataFormatSpec('raw', 'bin')
	RAW_SVC = _DataFormatSpec('raw:svc', 'svc.bin')
	SOURCE = _DataFormatSpec('source', 'asm')
	@classmethod
	def guess(cls, path):
		formats = sorted(cls, key=lambda format: len(format.extension), reverse=True)
		for format in formats:
			if path.endswith('.' + format.extension):
				break
		else:
			format = cls.RAW
		if format.extension.endswith('exe'):
			with open(path, 'rb') as file_h:
				if file_h.read(2) != b'MZ':
					format = cls.RAW
		return format