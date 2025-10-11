# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2025 Panos Kittenis and contributors.
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


import unittest
from unittest.mock import patch
from gevent import joinall

from pssh.clients import ParallelSSHClient, SSHClient
from pssh.exceptions import InvalidAPIUseError, UnknownHostError


class APIUseTest(unittest.TestCase):

    @patch('gevent.socket')
    @patch('pssh.clients.native.single.Session')
    def test_kbd_interactive_enabled_single_clients(self, mock_sess, mock_sock):
        self.assertRaises(UnknownHostError, SSHClient,
            'fakehost', password='fake_pass', keyboard_interactive=True, num_retries=0,
            timeout=.1,
            retry_delay=.1,
            _auth_thread_pool=False,
            allow_agent=False,
        )
        self.assertRaises(InvalidAPIUseError, SSHClient, 'fakehost', keyboard_interactive=True)

    @patch('gevent.socket')
    @patch('pssh.clients.native.single.Session')
    def test_kbd_interactive_enabled_parallel_clients(self, mock_sess, mock_sock):
        client = ParallelSSHClient(
            ['fakehost'], password='fake_pass', keyboard_interactive=True, num_retries=0,
            timeout=.1,
            retry_delay=.1,
            allow_agent=False,
        )
        self.assertRaises(UnknownHostError, client.run_command, 'echo me')
        self.assertRaises(InvalidAPIUseError, ParallelSSHClient, ['fakehost'], keyboard_interactive=True)
