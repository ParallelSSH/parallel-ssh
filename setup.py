# Copyright (C) 2014- Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

from setuptools import setup, find_packages
import sys

import versioneer

convert_2_to_3 = {}
if sys.version_info >= (3,):
    convert_2_to_3['use_2to3'] = True

setup(name='parallel-ssh',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='Asynchronous parallel SSH library',
      author='Panos Kittenis',
      author_email='22e889d8@opayq.com',
      url="https://github.com/pkittenis/parallel-ssh",
      packages=find_packages('.', exclude=(
          'embedded_server', 'embedded_server.*')),
      install_requires=['paramiko', 'gevent'],
      extras_require={':python_version < "3"': ['gevent<=1.1'],
                      ':python_version >= "3"': ['gevent>=1.1'],
                      },
      classifiers=[
        'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: BSD',
        'Operating System :: Microsoft :: Windows',
        ],
        **convert_2_to_3
      )
