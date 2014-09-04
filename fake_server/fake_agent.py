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
