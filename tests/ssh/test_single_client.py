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

from gevent import sleep, Timeout as GTimeout, spawn
from ssh.session import Session
from pssh.exceptions import AuthenticationException, ConnectionErrorException, \
    SessionError, SFTPIOError, SFTPError, SCPError, PKeyFileError, Timeout, \
    AuthenticationError
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

    def test_open_session_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           timeout=1)
        def _session(timeout=2):
            sleep(2)
        client.open_session = _session
        self.assertRaises(GTimeout, client.run_command, self.cmd)

    def test_execute(self):
        host_out = self.client.run_command(self.cmd)
        output = list(host_out.stdout)
        stderr = list(host_out.stderr)
        expected = [self.resp]
        self.assertEqual(expected, output)
        exit_code = host_out.channel.get_exit_status()
        self.assertEqual(exit_code, 0)

    def test_finished(self):
        self.assertFalse(self.client.finished(None))
        host_out = self.client.run_command(self.cmd)
        channel = host_out.channel
        self.assertFalse(self.client.finished(channel))
        self.assertRaises(ValueError, self.client.wait_finished, host_out.channel)
        self.client.wait_finished(host_out)
        stdout = list(host_out.stdout)
        self.assertTrue(self.client.finished(channel))
        self.assertListEqual(stdout, [self.resp])
        self.assertRaises(ValueError, self.client.wait_finished, None)
        host_out.channel = None
        self.assertIsNone(self.client.wait_finished(host_out))

    def test_finished_error(self):
        self.assertRaises(ValueError, self.client.wait_finished, None)
        self.assertIsNone(self.client.finished(None))

    def test_stderr(self):
        host_out = self.client.run_command('echo "me" >&2')
        self.client.wait_finished(host_out)
        output = list(host_out.stdout)
        stderr = list(host_out.stderr)
        expected = ['me']
        self.assertListEqual(expected, stderr)
        self.assertEqual(len(output), 0)

    def test_long_running_cmd(self):
        host_out = self.client.run_command('sleep 2; exit 2')
        self.assertRaises(ValueError, self.client.wait_finished, host_out.channel)
        self.client.wait_finished(host_out)
        exit_code = host_out.exit_code
        self.assertEqual(exit_code, 2)

    def test_wait_finished_timeout(self):
        host_out = self.client.run_command('sleep 2')
        timeout = 1
        self.assertFalse(self.client.finished(host_out.channel))
        start = datetime.now()
        self.assertRaises(Timeout, self.client.wait_finished, host_out, timeout=timeout)
        dt = datetime.now() - start
        self.assertTrue(timeout*1.05 > dt.total_seconds() > timeout)
        self.client.wait_finished(host_out)
        self.assertTrue(self.client.finished(host_out.channel))

    def test_client_disconnect_on_del(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client_sock = client.sock
        del client
        self.assertTrue(client_sock.closed)

    def test_client_bad_sock(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client.disconnect()
        client.sock = None
        self.assertIsNone(client.poll())

    def test_client_read_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        host_out = client.run_command('sleep 2; echo me', timeout=0.2)
        self.assertRaises(Timeout, list, host_out.stdout)

    def test_multiple_clients_exec_terminates_channels(self):
        # See #200 - Multiple clients should not interfere with
        # each other. session.disconnect can leave state in library
        # and break subsequent sessions even on different socket and
        # session
        def scope_killer():
            for _ in range(5):
                client = SSHClient(self.host, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1,
                                   allow_agent=False)
                host_out = client.run_command(self.cmd)
                output = list(host_out.stdout)
                self.assertListEqual(output, [self.resp])
        scope_killer()

    def test_interactive_shell(self):
        with self.client.open_shell() as shell:
            shell.run(self.cmd)
            shell.run(self.cmd)
        stdout = list(shell.output.stdout)
        self.assertListEqual(stdout, [self.resp, self.resp])
        self.assertEqual(shell.output.exit_code, 0)

    def test_interactive_shell_exit_code(self):
        with self.client.open_shell() as shell:
            shell.run(self.cmd)
            shell.run('sleep 1')
            shell.run(self.cmd)
            shell.run('exit 1')
        stdout = list(shell.output.stdout)
        self.assertListEqual(stdout, [self.resp, self.resp])
        self.assertEqual(shell.output.exit_code, 1)

    def test_password_auth_failure(self):
        self.assertRaises(AuthenticationError,
                          SSHClient, self.host, port=self.port, num_retries=1,
                          allow_agent=False,
                          password='blah blah blah')

    def test_open_session_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=2,
                           timeout=1)
        def _session(timeout=2):
            sleep(2)
        client.open_session = _session
        self.assertRaises(GTimeout, client.run_command, self.cmd)

    def test_connection_timeout(self):
        cmd = spawn(SSHClient, 'fakehost.com', port=12345,
                    retry_delay=1,
                    num_retries=2, timeout=1, _auth_thread_pool=False)
        # Should fail within greenlet timeout, otherwise greenlet will
        # raise timeout which will fail the test
        self.assertRaises(ConnectionErrorException, cmd.get, timeout=5)

    def test_client_read_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        host_out = client.run_command('sleep 2; echo me', timeout=0.2)
        self.assertRaises(Timeout, list, host_out.stdout)

    def test_open_session_exc(self):
        class Error(Exception):
            pass
        def _session():
            raise Error
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client._open_session = _session
        self.assertRaises(SessionError, client.open_session)

    def test_invalid_mkdir(self):
        self.assertRaises(OSError, self.client._make_local_dir, '/my_new_dir')

    # TODO:
    # * disconnect exc
