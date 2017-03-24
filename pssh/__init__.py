#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2014-2017 Panos Kittenis

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

"""Asynchronous parallel SSH client library.

Run SSH commands over many - hundreds/hundreds of thousands - number of servers
asynchronously and with minimal system load on the client host.

New users should start with
:py:func:`pssh.pssh_client.ParallelSSHClient.run_command`

See also :py:class:`pssh.ParallelSSHClient` and :py:class:mod:`pssh.SSHClient`
for class documentation.
"""

# flake8: noqa: E402, F401, F402

import logging
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
from .pssh_client import ParallelSSHClient
from .ssh_client import SSHClient
from .utils import enable_host_logger
from .exceptions import UnknownHostException, \
     AuthenticationException, ConnectionErrorException, SSHException

host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger('pssh')
if hasattr(logging, 'NullHandler'):
    host_logger.addHandler(logging.NullHandler())
    logger.addHandler(logging.NullHandler())
