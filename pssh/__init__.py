# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2020 Panos Kittenis.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""Asynchronous parallel SSH client library.

Run SSH commands over many - hundreds/hundreds of thousands - number of servers
asynchronously and with minimal system load on the client host.

New users should start with `pssh.clients.ParallelSSHClient.run_command` and
`pssh.clients.SSHClient.run_command`

See also `pssh.clients.ParallelSSHClient` and pssh.clients.SSHClient`
for class documentation.
"""


from logging import getLogger, NullHandler
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

host_logger = getLogger('pssh.host_logger')
logger = getLogger('pssh')
host_logger.addHandler(NullHandler())
logger.addHandler(NullHandler())
