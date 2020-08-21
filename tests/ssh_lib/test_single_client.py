# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2018 Panos Kittenis
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

from ssh.session import Session
# from ssh.exceptions import SocketDisconnectError
from pssh.exceptions import AuthenticationException, ConnectionErrorException, \
    SessionError, SFTPIOError, SFTPError, SCPError, PKeyFileError, Timeout
from pssh.clients.ssh_lib.single import SSHClient, logger as ssh_logger

from ..embedded_server.openssh import OpenSSHServer
from .base_ssh_case import SSHTestCase


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class SSHClientTest(SSHTestCase):

    def test_context_manager(self):
        with SSHClient(self.host, port=self.port,
                       pkey=self.user_key,
                       num_retries=1) as client:
            self.assertIsInstance(client, SSHClient)

    def test_execute(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            self.cmd)
        output = list(stdout)
        stderr = list(stderr)
        expected = [self.resp]
        self.assertEqual(expected, output)
        exit_code = channel.get_exit_status()
        self.assertEqual(exit_code, 0)

    def test_stderr(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'echo "me" >&2')
        self.client.wait_finished(channel)
        output = list(stdout)
        stderr = list(stderr)
        expected = ['me']
        self.assertListEqual(expected, stderr)
        self.assertEqual(len(output), 0)

    def test_long_running_cmd(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'sleep 2; exit 2')
        self.client.wait_finished(channel)
        exit_code = channel.get_exit_status()
        self.assertEqual(exit_code, 2)

    def test_client_wait_finished_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           timeout=0.6)
        chan = client.execute('sleep 1')
        self.assertRaises(Timeout, client.wait_finished, chan)

    def test_client_exec_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           timeout=0.00001)
        self.assertRaises(Timeout, client.execute, self.cmd)

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
                           num_retries=1,
                           timeout=0.2)
        channel, host, stdout, stderr, stdin = client.run_command(
            'sleep 2; echo me')
        output_gen = client.read_output(channel)
        self.assertRaises(Timeout, list, output_gen)
