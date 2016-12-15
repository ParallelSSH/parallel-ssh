#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2015 Panos Kittenis

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

"""Asynchronous parallel SSH library

parallel-ssh uses asychronous network requests - there is *no* multi-threading nor multi-processing used.

This is a *requirement* for commands on many (hundreds/thousands/hundreds of thousands) of hosts which would grind a system to a halt simply by having so many processes/threads all wanting to execute if done with multi-threading/processing.

The `libev event loop library <http://software.schmorp.de/pkg/libev.html>`_ is utilised on nix systems. Windows is not supported.

See :mod:`pssh.ParallelSSHClient` and :mod:`pssh.SSHClient` for class documentation.
"""

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
from .pssh_client import ParallelSSHClient
from .ssh_client import SSHClient
from .utils import enable_host_logger
from .exceptions import UnknownHostException, \
     AuthenticationException, ConnectionErrorException, SSHException
import logging

host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger('pssh')
