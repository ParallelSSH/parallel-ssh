# Copyright (C) 2014-2018 Panos Kittenis.

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

import os
import platform
from setuptools import setup, find_packages
from platform import python_version

import versioneer

try:
    from Cython.Distutils.extension import Extension
    from Cython.Distutils import build_ext
except ImportError:
    from setuptools import Extension
    USING_CYTHON = False
else:
    USING_CYTHON = True


ON_WINDOWS = platform.system() == 'Windows'

gevent_req = 'gevent<=1.1' if python_version() < '2.7' else 'gevent>=1.1'

cython_directives = {'embedsignature': True,
                     'boundscheck': False,
                     'optimize.use_switch': True,
                     'wraparound': False,
}

cython_args = {'cython_directives': cython_directives} if USING_CYTHON else {}

ext = 'pyx' if USING_CYTHON else 'c'
_comp_args = ["-O3"] if not ON_WINDOWS else None

extensions = [
    Extension('pssh.native._ssh2',
              sources=['pssh/native/_ssh2.%s' % ext],
              extra_compile_args=_comp_args,
              **cython_args
    )]

cmdclass = versioneer.get_cmdclass()
if USING_CYTHON:
    cmdclass['build_ext'] = build_ext

setup(name='parallel-ssh',
      version=versioneer.get_version(),
      cmdclass=cmdclass,
      description='Asynchronous parallel SSH library',
      long_description=open('README.rst').read(),
      author='Panos Kittenis',
      author_email='22e889d8@opayq.com',
      url="https://github.com/ParallelSSH/parallel-ssh",
      packages=find_packages(
          '.', exclude=('embedded_server', 'embedded_server.*',
                        'tests', 'tests.*',
                        '*.tests', '*.tests.*')
      ),
      install_requires=['paramiko', gevent_req, 'ssh2-python>=0.17.0'],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          'Programming Language :: C',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: System :: Networking',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Operating System :: POSIX :: Linux',
          'Operating System :: POSIX :: BSD',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: MacOS :: MacOS X',
      ],
      ext_modules=extensions,
)
