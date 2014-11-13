#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2014 Panos Kittenis

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

"""Unittests for :mod:`pssh.ParallelSSHClient` class"""

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
        self.long_running_cmd = 'long running'
        self.user_key = USER_KEY
        self.listen_socket = make_socket('127.0.0.1')
        self.listen_port = self.listen_socket.getsockname()[1]

    def long_running_response(self, responses):
        i = 0
        while True:
            if i >= responses:
                raise StopIteration
            gevent.sleep(0)
            yield 'long running response'
            gevent.sleep(1)
            i += 1
            
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
                
    def test_pssh_client_long_running_command(self):
        expected_lines = 5
        server = start_server({ self.long_running_cmd :
                                self.long_running_response(expected_lines) },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        cmd = client.exec_command(self.long_running_cmd)[0]
        output = client.get_stdout(cmd)
        self.assertTrue('127.0.0.1' in output, msg="Got no output for command")
        stdout = list(output['127.0.0.1']['stdout'])
        self.assertTrue(len(stdout) == expected_lines, msg="Expected %s lines of response, got %s" %
                        (expected_lines, len(stdout)))
        del client
        server.kill()
        
    def test_pssh_client_retries(self):
        """Test connection error retries"""
        expected_num_tries = 2
        with self.assertRaises(ConnectionErrorException) as cm:
            client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                       pkey=self.user_key, num_retries=expected_num_tries)
            cmd = client.exec_command('blah')[0]
            cmd.get()
        num_tries = cm.exception.args[-1:][0]
        self.assertEqual(expected_num_tries, num_tries,
                         msg="Got unexpected number of retries %s - expected %s"
                         % (num_tries, expected_num_tries,))

    def test_pssh_copy_file(self):
        """Test parallel copy file"""
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filename = 'remote_test_dir', 'test_file_copy'
        remote_filename = os.path.sep.join([remote_test_dir, remote_filename])
        test_file = open(local_filename, 'w')
        test_file.writelines([test_file_data + os.linesep])
        test_file.close()
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        cmds = client.copy_file(local_filename, remote_filename)
        cmds[0].get()
        self.assertTrue(os.path.isdir(remote_test_dir),
                        msg="SFTP create remote directory failed")
        self.assertTrue(os.path.isfile(remote_filename),
                        msg="SFTP copy failed")
        for filepath in [local_filename, remote_filename]:
            os.unlink(filepath)
        del client
        server.join()
