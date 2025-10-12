#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


import unittest
from unittest.mock import patch, MagicMock

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

    @patch('gevent.socket.socket')
    @patch('pssh.clients.native.single.Session')
    def test_kbd_interactive_enabled_and_used(self, mock_sess, mock_sock):
        sess = MagicMock()
        mock_sess.return_value = sess
        kbd_auth = MagicMock()
        password_auth = MagicMock()
        sess.userauth_keyboardinteractive = kbd_auth
        sess.userauth_password = password_auth
        my_user = "my_user"
        my_pass = "fake_pass"

        client = SSHClient(
            '127.0.0.1', port=1234, user=my_user, password=my_pass, keyboard_interactive=True, num_retries=0,
            timeout=.1,
            retry_delay=.1,
            _auth_thread_pool=False,
            allow_agent=False,
            identity_auth=False,
        )
        sess.userauth_keyboardinteractive.assert_called_once_with(my_user, my_pass)
        sess.userauth_password.assert_not_called()
        self.assertEqual(client.user, my_user)
        self.assertEqual(client.password, my_pass)
