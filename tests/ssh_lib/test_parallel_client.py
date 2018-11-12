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
import os
import pwd
import logging
import time
import subprocess

from gevent import socket, sleep, spawn, joinall
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError, PKeyFileError
from pssh import logger as pssh_logger
from pssh.clients.ssh_lib.parallel import ParallelSSHClient, logger as ssh_logger

from .base_ssh_test import PKEY_FILENAME, PUB_FILE
from ..embedded_server.openssh import OpenSSHServer
from ..embedded_server.embedded_server import make_socket


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class LibSSHParallelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.host = '127.0.0.1'
        cls.port = 2223
        cls.server = OpenSSHServer(listen_ip=cls.host, port=cls.port)
        cls.server.start_server()
        cls.cmd = 'echo me'
        cls.resp = u'me\n'
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
        del cls.client
        cls.server.stop()

    def setUp(self):
        self.long_cmd = lambda lines: 'for (( i=0; i<%s; i+=1 )) do echo $i; sleep 1; done' % (lines,)

    def make_random_port(self, host=None):
        host = self.host if not host else host
        listen_socket = make_socket(host)
        listen_port = listen_socket.getsockname()[1]
        listen_socket.close()
        return listen_port

    def test_client_join_stdout(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
        expected_stderr = []
        stdout = list(output[self.host].stdout)
        stderr = list(output[self.host].stderr)
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" %
                         (stdout, expected_stdout,))
        self.assertEqual(expected_stderr, stderr,
                         msg="Got unexpected stderr - %s, expected %s" %
                         (stderr, expected_stderr,))
        self.client.join(output)
        exit_code = output[self.host]['exit_code']
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code, expected_exit_code,))
        output = self.client.run_command(";".join([self.cmd, 'exit 1']))
        self.client.join(output)
        exit_code = output[self.host].exit_code
        self.assertTrue(exit_code == 1)
        self.assertTrue(len(output), len(self.client.cmds))
        _output = {}
        for i, host in enumerate([self.host]):
            cmd = self.client.cmds[i]
            self.client.get_output(cmd, _output)
        self.assertTrue(len(_output) == len(output))
        for host in output:
            self.assertTrue(host in _output)

    def test_pssh_client_run_long_command(self):
        expected_lines = 5
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.assertTrue(self.host in output, msg="Got no output for command")
        stdout = list(output[self.host]['stdout'])
        self.client.join(output)
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))
