#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2015 Panos Kittenis

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
     AuthenticationException, ConnectionErrorException, SSHException, logger as pssh_logger
from fake_server.fake_server import start_server, make_socket, \
     logger as server_logger, paramiko_logger
import random
import logging
import gevent
import threading
import paramiko
import os
import warnings

USER_KEY = paramiko.RSAKey.from_private_key_file(
    os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key']))

# server_logger.setLevel(logging.DEBUG)
# pssh_logger.setLevel(logging.DEBUG)
# logging.basicConfig()

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
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'127.0.0.1' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg="Got unexpected command output - %s" % (output,))
        del client
        server.join()

    def test_pssh_client_exec_command_get_buffers(self):
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
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
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" % 
                         (stdout,
                          expected_stdout,))
        self.assertEqual(expected_stderr, stderr,
                         msg="Got unexpected stderr - %s, expected %s" % 
                         (stderr,
                          expected_stderr,))
        del client
        server.join()

    def test_pssh_client_run_command_get_output(self):
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        output = client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        exit_code = output['127.0.0.1']['exit_code']
        stdout = list(output['127.0.0.1']['stdout'])
        stderr = list(output['127.0.0.1']['stderr'])
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" %
                         (stdout,
                          expected_stdout,))
        self.assertEqual(expected_stderr, stderr,
                         msg="Got unexpected stderr - %s, expected %s" %
                         (stderr,
                          expected_stderr,))
        del client
        server.join()

    def test_pssh_client_run_command_get_output_explicit(self):
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        out = client.run_command(self.fake_cmd)
        cmds = [cmd for host in out for cmd in [out[host]['cmd']]]
        output = client.get_output(commands=cmds)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        exit_code = output['127.0.0.1']['exit_code']
        stdout = list(output['127.0.0.1']['stdout'])
        stderr = list(output['127.0.0.1']['stderr'])
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" % 
                         (stdout,
                          expected_stdout,))
        self.assertEqual(expected_stderr, stderr,
                         msg="Got unexpected stderr - %s, expected %s" % 
                         (stderr,
                          expected_stderr,))
        del client
        server.join()

    def test_pssh_client_run_long_command(self):
        expected_lines = 5
        server = start_server({ self.long_running_cmd :
                                self.long_running_response(expected_lines) },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key)
        output = client.run_command(self.long_running_cmd)
        self.assertTrue('127.0.0.1' in output, msg="Got no output for command")
        stdout = list(output['127.0.0.1']['stdout'])
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))
        del client
        server.kill()

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

    def test_pssh_client_ssh_exception(self):
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket,
                              ssh_exception=True)
        client = ParallelSSHClient(['127.0.0.1'],
                                   user='fakey', password='fakey',
                                   port=self.listen_port,
                                   pkey=paramiko.RSAKey.generate(1024),
                                   )
        # Handle exception
        try:
            client.run_command(self.fake_cmd)
            raise Exception("Expected SSHException, got none")
        except SSHException:
            pass
        del client
        server.join()

    def test_pssh_client_timeout(self):
        server_timeout=0.2
        client_timeout=server_timeout-0.1
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket,
                              timeout=server_timeout)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key,
                                   timeout=client_timeout)
        output = client.run_command(self.fake_cmd)
        # Handle exception
        try:
            gevent.sleep(server_timeout+0.2)
            client.pool.join()
            if not server.exception:
                raise Exception(
                    "Expected gevent.Timeout from socket timeout, got none")
            raise server.exception
        except gevent.Timeout:
            pass
        chan_timeout = output['127.0.0.1']['channel'].gettimeout()
        self.assertEqual(client_timeout, chan_timeout,
                         msg="Channel timeout %s does not match requested timeout %s" %(
                             chan_timeout, client_timeout,))
        del client
        server.join()

    def test_pssh_client_exec_command_password(self):
        """Test password authentication. Fake server accepts any password
        even empty string"""
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   password='')
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'127.0.0.1' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg="Got unexpected command output - %s" % (output,))
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
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))
        del client
        server.kill()
        
    def test_pssh_client_retries(self):
        """Test connection error retries"""
        expected_num_tries = 2
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key,
                                   num_retries=expected_num_tries)
        self.assertRaises(ConnectionErrorException, client.run_command, 'blah')
        try:
            client.run_command('blah')
        except ConnectionErrorException, ex:
            num_tries = ex.args[-1:][0]
            self.assertEqual(expected_num_tries, num_tries,
                             msg="Got unexpected number of retries %s - expected %s"
                             % (num_tries, expected_num_tries,))
        else:
            raise Exception('No ConnectionErrorException')

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

    def test_pssh_pool_size(self):
        """Test pool size logic"""
        hosts = ['host-%01d' % d for d in xrange(5)]
        client = ParallelSSHClient(hosts)
        expected, actual = len(hosts), client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))
        hosts = ['host-%01d' % d for d in xrange(15)]
        client = ParallelSSHClient(hosts)
        expected, actual = client.pool_size, client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))
        hosts = ['host-%01d' % d for d in xrange(15)]
        client = ParallelSSHClient(hosts, pool_size=len(hosts)+5)
        expected, actual = len(hosts), client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))

    def test_pssh_hosts_more_than_pool_size(self):
        """Test we can successfully run on more hosts than our pool size and
        get logs for all hosts"""
        # Make a second server on the same port as the first one
        server2_socket = make_socket('127.0.0.2', port=self.listen_port)
        server2_port = server2_socket.getsockname()[1]
        server1 = start_server({ self.fake_cmd : self.fake_resp },
                               self.listen_socket)
        server2 = start_server({ self.fake_cmd : self.fake_resp },
                               server2_socket)
        hosts = ['127.0.0.1', '127.0.0.2']
        client = ParallelSSHClient(hosts,
                                   port=self.listen_port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.fake_cmd)
        stdout = [list(output[k]['stdout']) for k in output]
        expected_stdout = [[self.fake_resp], [self.fake_resp]]
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for \
%s/%s hosts" % (len(output), len(hosts),))
        self.assertEqual(expected_stdout, stdout,
                         msg="Did not get expected output from all hosts. \
                         Got %s - expected %s" % (stdout, expected_stdout,))
        del client
        server1.kill()
        server2.kill()

    def test_ssh_proxy(self):
        """Test connecting to remote destination via SSH proxy
        client -> proxy -> destination
        Proxy SSH server accepts no commands and sends no responses, only
        proxies to destination. Destination accepts a command as usual."""
        proxy_server_socket = make_socket('127.0.0.1')
        proxy_server_port = proxy_server_socket.getsockname()[1]
        proxy_server = start_server({}, proxy_server_socket)
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient(['127.0.0.1'], port=self.listen_port,
                                   pkey=self.user_key,
                                   proxy_host='127.0.0.1',
                                   proxy_port=proxy_server_port
                                   )
        output = client.run_command(self.fake_cmd)
        stdout = list(output['127.0.0.1']['stdout'])
        expected_stdout = [self.fake_resp]
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" % 
                         (stdout,
                          expected_stdout,))
        server.kill()
        proxy_server.kill()
