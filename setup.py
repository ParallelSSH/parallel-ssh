"""
Copyright (C) 2014 Panos Kittenis

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation, version 2.1.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
"""

from distutils.core import setup
from setuptools import find_packages

setup(name='parallel-ssh',
      version='0.5',
      description='Wrapper library over paramiko to allow remote execution of tasks. Supports parallel execution on multiple hosts',
      author='Panos Kittenis',
      author_email='pkittenis@gmail.com',
      url = "https://github.com/pkittenis/parallel-ssh",
      py_modules = ['pssh'],
      install_requires = ['paramiko', 'gevent'],
      classifiers = [
        'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: BSD',
        ],
      )
