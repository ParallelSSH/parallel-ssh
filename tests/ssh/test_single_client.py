# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2020 Panos Kittenis
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
import logging

from datetime import datetime

from ssh.session import Session
# from ssh.exceptions import SocketDisconnectError
from pssh.exceptions import AuthenticationException, ConnectionErrorException, \
    SessionError, SFTPIOError, SFTPError, SCPError, PKeyFileError, Timeout
from pssh.clients.ssh.single import SSHClient, logger as ssh_logger

from .base_ssh_case import SSHTestCase
from ..embedded_server.openssh import OpenSSHServer

ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class SSHClientTest(SSHTestCase):

    def test_context_manager(self):
        with SSHClient(self.host, port=self.port,
                       pkey=self.user_key,
                       num_retries=1) as client:
            self.assertIsInstance(client, SSHClient)

    def test_execute(self):
        host_out = self.client.run_command(self.cmd)
        output = list(host_out.stdout)
        stderr = list(host_out.stderr)
        expected = [self.resp]
        self.assertEqual(expected, output)
        exit_code = host_out.channel.get_exit_status()
        self.assertEqual(exit_code, 0)

    def test_finished_error(self):
        self.assertIsNone(self.client.wait_finished(None))
        self.assertIsNone(self.client.finished(None))

    def test_stderr(self):
        host_out = self.client.run_command('echo "me" >&2')
        self.client.wait_finished(host_out.channel)
        output = list(host_out.stdout)
        stderr = list(host_out.stderr)
        expected = ['me']
        self.assertListEqual(expected, stderr)
        self.assertEqual(len(output), 0)

    def test_long_running_cmd(self):
        host_out = self.client.run_command('sleep 2; exit 2')
        self.client.wait_finished(host_out.channel)
        exit_code = host_out.exit_code
        self.assertEqual(exit_code, 2)

    def test_wait_finished_timeout(self):
        channel = self.client.execute('sleep 2')
        timeout = 1
        self.assertFalse(self.client.finished(channel))
        start = datetime.now()
        self.assertRaises(Timeout, self.client.wait_finished, channel, timeout=timeout)
        dt = datetime.now() - start
        self.assertTrue(timeout*1.05 > dt.total_seconds() > timeout)
        self.client.wait_finished(channel)
        self.assertTrue(self.client.finished(channel))

    def test_client_disconnect_on_del(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client_sock = client.sock
        del client
        self.assertTrue(client_sock.closed)

    def test_client_read_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        host_out = client.run_command('sleep 2; echo me', timeout=0.2)
        self.assertRaises(Timeout, list, host_out.stdout)

    def test_multiple_clients_exec_terminates_channels(self):
        # See #200 - Multiple clients should not interfere with
        # each other. session.disconnect can leave state in libssh2
        # and break subsequent sessions even on different socket and
        # session
        def scope_killer():
            for _ in range(5):
                client = SSHClient(self.host, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1,
                                   allow_agent=False)
                channel = client.execute(self.cmd)
                output = list(client.read_output(channel))
                self.assertListEqual(output, [b'me'])
        scope_killer()

    # TODO:
    # * read timeouts
    # * session connect retry
    # * agent auth success
    # * password auth failure
    # * open session error
    # * disconnect exc
