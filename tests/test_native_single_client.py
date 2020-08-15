import unittest
import os
import logging
import time
import subprocess

from gevent import socket, sleep, spawn

from .base_ssh2_test import SSH2TestCase
from .embedded_server.openssh import OpenSSHServer
from pssh.clients.native import SSHClient, logger as ssh_logger
from ssh2.session import Session
from ssh2.channel import Channel
from ssh2.exceptions import SocketDisconnectError, BannerRecvError, SocketRecvError
from pssh.exceptions import AuthenticationException, ConnectionErrorException, \
    SessionError, SFTPIOError, SFTPError, SCPError, PKeyFileError, Timeout


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class SSH2ClientTest(SSH2TestCase):

    def test_context_manager(self):
        with SSHClient(self.host, port=self.port,
                       pkey=self.user_key,
                       num_retries=1) as client:
            self.assertIsInstance(client, SSHClient)

    def test_sftp_fail(self):
        sftp = self.client._make_sftp()
        self.assertRaises(SFTPIOError, self.client._mkdir, sftp, '/blah')
        self.assertRaises(SFTPError, self.client.sftp_put, sftp, 'a file', '/blah')

    def test_scp_fail(self):
        self.assertRaises(SCPError, self.client.scp_recv, 'fakey', 'fake')
        try:
            os.mkdir('adir')
        except OSError:
            pass
        try:
            self.assertRaises(ValueError, self.client.scp_send, 'adir', 'fake')
        finally:
            os.rmdir('adir')

    def test_execute(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            self.cmd)
        output = list(stdout)
        stderr = list(stderr)
        expected = [self.resp]
        exit_code = channel.get_exit_status()
        self.assertEqual(exit_code, 0)
        self.assertEqual(expected, output)

    def test_stderr(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'echo "me" >&2')
        self.client.wait_finished(channel)
        output = list(stdout)
        stderr = list(stderr)
        expected = ['me']
        self.assertListEqual(expected, stderr)
        self.assertTrue(len(output) == 0)

    def test_long_running_cmd(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'sleep 2; exit 2')
        self.client.wait_finished(channel)
        exit_code = channel.get_exit_status()
        self.assertEqual(exit_code, 2)

    def test_manual_auth(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           allow_agent=False)
        client.session.disconnect()
        del client.session
        del client.sock
        client.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client._connect(self.host, self.port)
        client._init()
        # Identity auth
        client.pkey = None
        client.session.disconnect()
        del client.session
        del client.sock
        client.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client._connect(self.host, self.port)
        client.session = Session()
        client.session.handshake(client.sock)
        self.assertRaises(AuthenticationException, client.auth)

    def test_failed_auth(self):
        self.assertRaises(PKeyFileError, SSHClient, self.host, port=self.port,
                          pkey='client_pkey',
                          num_retries=1)
        self.assertRaises(PKeyFileError, SSHClient, self.host, port=self.port,
                          pkey='~/fake_key',
                          num_retries=1)

    def test_handshake_fail(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client.session.disconnect()
        self.assertRaises((SocketDisconnectError, BannerRecvError, SocketRecvError), client._init)

    def test_stdout_parsing(self):
        dir_list = os.listdir(os.path.expanduser('~'))
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'ls -la')
        output = list(stdout)
        # Output of `ls` will have 'total', '.', and '..' in addition to dir
        # listing
        self.assertEqual(len(dir_list), len(output) - 3)

    def test_file_output_parsing(self):
        lines = int(subprocess.check_output(
            ['wc', '-l', 'pssh/native/_ssh2.c']).split()[0])
        dir_name = os.path.dirname(__file__)
        ssh2_file = os.sep.join((dir_name, '..', 'pssh', 'native', '_ssh2.c'))
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'cat %s' % ssh2_file)
        output = list(stdout)
        self.assertEqual(lines, len(output))

    def test_identity_auth_failure(self):
        self.assertRaises(AuthenticationException,
                          SSHClient, self.host, port=self.port, num_retries=1,
                          allow_agent=False)

    @unittest.skipUnless(bool(os.getenv('TRAVIS')),
                         "Not on Travis-CI - skipping agent auth failure test")
    def test_agent_auth_failure(self):
        self.assertRaises(AuthenticationException,
                          SSHClient, self.host, port=self.port, num_retries=1,
                          allow_agent=True)

    def test_password_auth_failure(self):
        self.assertRaises(AuthenticationException,
                          SSHClient, self.host, port=self.port, num_retries=1,
                          allow_agent=False,
                          password='blah blah blah')

    def test_retry_failure(self):
        self.assertRaises(ConnectionErrorException,
                          SSHClient, self.host, port=12345,
                          num_retries=2, _auth_thread_pool=False)

    def test_connection_timeout(self):
        cmd = spawn(SSHClient, 'fakehost.com', port=12345,
                    num_retries=1, timeout=1, _auth_thread_pool=False)
        # Should fail within greenlet timeout, otherwise greenlet will
        # raise timeout which will fail the test
        self.assertRaises(ConnectionErrorException, cmd.get, timeout=2)
