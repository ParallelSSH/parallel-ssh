#!/usr/bin/env python

"""Unittests for parallel-ssh

Copyright (C) 2014 Panos Kittenis

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation, version 2.1.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
"""

import unittest
from pssh import ParallelSSHClient, UnknownHostException, \
    AuthenticationException, ConnectionErrorException
from fake_server.fake_server import start_server, make_socket, logger as server_logger, \
    paramiko_logger
import random
import logging
import gevent
import threading
import paramiko
import os

USER_KEY = paramiko.RSAKey.from_private_key_file(
    os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key']))

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'
        self.user_key = USER_KEY
        self.listen_socket = make_socket('127.0.0.1')
        self.listen_port = self.listen_socket.getsockname()[1]

    def tearDown(self):
        del self.listen_socket
        
    def test_pssh_client_exec_command(self):
        server = start_server({ self.fake_cmd : self.fake_resp }, self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'127.0.0.1' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        del client
        server.join()

    def test_pssh_client_exec_command_get_buffers(self):
        server = start_server({ self.fake_cmd : self.fake_resp }, self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd, return_buffers=True)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        exit_code = output['127.0.0.1']['exit_code']
        stdout = list(output['127.0.0.1']['stdout'])
        stderr = list(output['127.0.0.1']['stderr'])
        self.assertEqual(expected_exit_code, exit_code,
                         msg = "Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))
        self.assertEqual(expected_stdout, stdout,
                         msg = "Got unexpected stdout - %s, expected %s" % 
                         (stdout,
                          expected_stdout,))
        self.assertEqual(expected_stderr, stderr,
                         msg = "Got unexpected stderr - %s, expected %s" % 
                         (stderr,
                          expected_stderr,))
        del client
        server.join()

    def test_pssh_client_auth_failure(self):
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket, fail_auth=True)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        cmd = client.exec_command(self.fake_cmd)[0]
        # Handle exception
        try:
            cmd.get()
            raise Exception("Expected AuthenticationException, got none")
        except AuthenticationException:
            pass
        del client
        server.join()

    def test_pssh_client_exec_command_password(self):
        """Test password authentication. Fake server accepts any password
        even empty string"""
        server = start_server({ self.fake_cmd : self.fake_resp }, self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   password='')
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'127.0.0.1' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        del client
        server.join()
