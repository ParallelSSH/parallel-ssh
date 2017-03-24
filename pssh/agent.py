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

"""SSH agent module of ParallelSSH"""

import paramiko.agent


class SSHAgent(paramiko.agent.AgentSSH):
    """:py:class:`paramiko.agent.Agent` compatible class for programmatically
    supplying an SSH agent"""

    def __init__(self):
        """**Example Usage**

        .. code-block:: python

          from pssh.agent import SSHAgent
          from pssh.utils import load_private_key
          from pssh import ParallelSSHClient

          agent = SSHAgent()
          agent.add_key(load_private_key('my_private_key_filename'))
          agent.add_key(load_private_key('my_other_private_key_filename'))
          hosts = ['my_host', 'my_other_host']

          client = ParallelSSHClient(hosts, agent=agent)
          client.run_command('uname')
        """
        paramiko.agent.AgentSSH.__init__(self)
        self._conn = None
        self.keys = []

    def add_key(self, key):
        """Add key to agent.

        :param key: Key to add
        :type key: :py:class:`paramiko.pkey.PKey`
        """
        self.keys.append(key)

    def _connect(self, conn):
        pass

    def _close(self):
        self._keys = []

    def get_keys(self):
        return tuple(self.keys)
