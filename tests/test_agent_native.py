# This file is part of parallel-ssh.

# Copyright (C) 2015-2018 Panos Kittenis

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

import unittest
import pwd
import logging
import os
from sys import version_info
from subprocess import call

from .embedded_server.openssh import OpenSSHServer
from .base_ssh2_test import PKEY_FILENAME, PUB_FILE

from pssh.pssh2_client import ParallelSSHClient, logger as pssh_logger

pssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class ForwardTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(PKEY_FILENAME, _mask)
        if call('ssh-add %s' % PKEY_FILENAME, shell=True) != 1:
            raise unittest.SkipTest("No agent available.")
        cls.server = OpenSSHServer()
        cls.server.start_server()
        cls.host = '127.0.0.1'
        cls.port = 2222
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.user = pwd.getpwuid(os.geteuid()).pw_name
        # Single client for all tests ensures that the client does not do
        # anything that causes server to disconnect the session and
        # affect all subsequent uses of the same session.
        cls.client = ParallelSSHClient([cls.host],
                                       pkey=PKEY_FILENAME,
                                       port=cls.port,
                                       num_retries=1)

    @classmethod
    def tearDownClass(cls):
        call('ssh-add -d %s' % PKEY_FILENAME, shell=True)
        cls.server.stop()
        del cls.server

    def test_agent_forwarding(self):
        client = ParallelSSHClient(['localhost'], forward_ssh_agent=True,
                                   port=self.port)
        output = client.run_command(self.cmd)
        stdout = [list(output['localhost'].stdout) for k in output]
        expected_stdout = [[self.resp]]
        self.assertListEqual(stdout, expected_stdout)
