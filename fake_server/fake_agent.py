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

"""
Fake SSH Agent for testing ssh agent forwarding and agent based key
authentication
"""

import paramiko.agent

class FakeAgent(paramiko.agent.AgentSSH):

    def __init__(self):
        self._conn = None
        self.keys = []
    
    def add_key(self, key):
        """Add key to agent.
        :param key: Key to add
        :type key: :mod:`paramiko.pkey.PKey`
        """
        self.keys.append(key)

    def _connect(self, conn):
        pass

    def _close(self):
        self._keys = []

    def get_keys(self):
        return tuple(self.keys)
