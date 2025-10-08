#!/usr/bin/env python3

# Part of mlat-client - an ADS-B multilateration client.
# Copyright 2015, Oliver Jowett <oliver@mutability.co.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys

# setuptools with python 3.9 is buggy or something
# only use setuptools for 3.10 and up as distutils is deprecated 3.12 and up

if sys.version_info.minor >= 10:
    from setuptools import setup, Extension
else:
    from distutils.core import setup, Extension

import platform
import os

# get the version from the source
CLIENT_VERSION = "unknown"
exec(open('mlat/client/version.py').read())

more_warnings = False
extra_compile_args = []

# Architecture detection and optimization
def get_optimization_flags():
    flags = []
    
    # Base optimization level
    if platform.system() == 'Linux':
        flags.append('-O3')
        
        # Get architecture from environment or detect
        arch = os.environ.get('TARGET_ARCH') or platform.machine()
        
        # Architecture-specific optimizations
        if arch in ['x86_64', 'amd64']:
            # Intel/AMD 64-bit
            if os.environ.get('OPTIMIZE_NATIVE'):
                flags.append('-march=native')
            else:
                flags.append('-march=x86-64')
                flags.append('-mtune=generic')
        elif arch in ['aarch64', 'arm64']:
            # ARM 64-bit
            if os.environ.get('OPTIMIZE_NATIVE'):
                flags.append('-march=native')
            else:
                flags.append('-march=armv8-a')
                flags.append('-mtune=generic')
        elif arch.startswith('arm'):
            # ARM 32-bit
            if os.environ.get('OPTIMIZE_NATIVE'):
                flags.append('-march=native')
            else:
                flags.append('-march=armv7-a')
                flags.append('-mfpu=neon')
                flags.append('-mtune=generic')
        
        # Enable Link Time Optimization if requested
        if os.environ.get('ENABLE_LTO'):
            flags.append('-flto')
            
        # Profile-guided optimization flags
        if os.environ.get('PGO_GENERATE'):
            flags.append('-fprofile-generate')
        elif os.environ.get('PGO_USE'):
            flags.append('-fprofile-use')
            flags.append('-fprofile-correction')
    
    # Add custom CFLAGS from environment
    if 'CFLAGS' in os.environ:
        flags.extend(os.environ['CFLAGS'].split())
    
    return flags

extra_compile_args = get_optimization_flags()

if more_warnings:
    # let's assume this is GCC
    extra_compile_args.append('-Wpointer-arith')

modes_ext = Extension('_modes',
                      sources=['_modes.c', 'modes_reader.c', 'modes_message.c', 'modes_crc.c'],
                      extra_compile_args=extra_compile_args)

setup(name='MlatClient',
      version=CLIENT_VERSION,
      description='Multilateration client package',
      author='Oliver Jowett',
      author_email='oliver@mutability.co.uk',
      packages=['mlat', 'mlat.client'],
      ext_modules=[modes_ext],
      scripts=['mlat-client'])
