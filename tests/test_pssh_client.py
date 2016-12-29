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
import random
import logging
import os
import warnings
import shutil
import sys

import gevent
from pssh import ParallelSSHClient, UnknownHostException, \
     AuthenticationException, ConnectionErrorException, SSHException, \
     logger as pssh_logger
from pssh.exceptions import HostArgumentException
from pssh.utils import load_private_key
from embedded_server.embedded_server import start_server, make_socket, \
     logger as server_logger, paramiko_logger
from embedded_server.fake_agent import FakeAgent
from paramiko import RSAKey

PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key'])
USER_KEY = RSAKey.from_private_key_file(PKEY_FILENAME)

server_logger.setLevel(logging.DEBUG)
pssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'echo "me"'
        self.fake_resp = 'me'
        self.long_cmd = lambda lines: 'for (( i=0; i<%s; i+=1 )) do echo $i; sleep 1; done' % (lines,)
        self.user_key = USER_KEY
        self.host = '127.0.0.1'
        self.listen_socket = make_socket(self.host)
        self.listen_port = self.listen_socket.getsockname()[1]
        self.server = start_server(self.listen_socket)
        self.agent = FakeAgent()
        self.agent.add_key(USER_KEY)
        self.client = ParallelSSHClient([self.host], port=self.listen_port,
                                        pkey=self.user_key,
                                        agent=self.agent)
    
    def tearDown(self):
        del self.server
        del self.listen_socket
        del self.client
    
    def test_pssh_client_exec_command(self):
        cmd = self.client.exec_command(self.fake_cmd)[0]
        output = self.client.get_stdout(cmd)
        self.assertTrue(self.host in output,
                        msg="No output for host")
        self.assertTrue(output[self.host]['exit_code'] == 0)

    def test_pssh_client_no_stdout_non_zero_exit_code_immediate_exit(self):
        output = self.client.run_command('exit 1')
        expected_exit_code = 1
        self.client.join(output)
        exit_code = output[self.host]['exit_code']
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))

    def test_pssh_client_exec_command_get_buffers(self):
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd, return_buffers=True)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        exit_code = output[self.host]['exit_code']
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
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

    def test_pssh_client_run_command_get_output(self):
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        output = client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        exit_code = output[self.host]['exit_code']
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

    def test_pssh_client_run_command_get_output_explicit(self):
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        out = client.run_command(self.fake_cmd)
        cmds = [cmd for host in out for cmd in [out[host]['cmd']]]
        output = {}
        for cmd in cmds:
            client.get_output(cmd, output)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        exit_code = output[self.host]['exit_code']
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

    def test_pssh_client_run_long_command(self):
        expected_lines = 5
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        output = client.run_command(self.long_cmd(expected_lines))
        self.assertTrue(self.host in output, msg="Got no output for command")
        stdout = list(output[self.host]['stdout'])
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))
        del client

    def test_pssh_client_auth_failure(self):
        listen_socket = make_socket(self.host)
        listen_port = listen_socket.getsockname()[1]
        server = start_server(listen_socket, fail_auth=True)
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        cmd = client.exec_command(self.fake_cmd)[0]
        # Handle exception
        try:
            cmd.get()
            raise Exception("Expected AuthenticationException, got none")
        except AuthenticationException:
            pass
        del client
        server.kill()

    def test_pssh_client_hosts_list_part_failure(self):
        """Test getting output for remainder of host list in the case where one
        host in the host list has a failure"""
        server2_socket = make_socket('127.0.0.2', port=self.listen_port)
        server2_port = server2_socket.getsockname()[1]
        server2 = start_server(server2_socket, fail_auth=True)
        hosts = [self.host, '127.0.0.2']
        client = ParallelSSHClient(hosts,
                                   port=self.listen_port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        output = client.run_command(self.fake_cmd,
                                    stop_on_errors=False)
        self.assertFalse(client.finished(output))
        client.join(output)
        self.assertTrue(client.finished(output))
        self.assertTrue(hosts[0] in output,
                        msg="Successful host does not exist in output - output is %s" % (output,))
        self.assertTrue(hosts[1] in output,
                        msg="Failed host does not exist in output - output is %s" % (output,))
        self.assertTrue('exception' in output[hosts[1]],
                        msg="Failed host %s has no exception in output - %s" % (hosts[1], output,))
        try:
            raise output[hosts[1]]['exception']
        except AuthenticationException:
            pass
        else:
            raise Exception("Expected AuthenticationException, got %s instead" % (
                output[hosts[1]]['exception'],))
        del client
        server2.kill()
    
    def test_pssh_client_ssh_exception(self):
        listen_socket = make_socket(self.host)
        listen_port = listen_socket.getsockname()[1]
        server = start_server(listen_socket,
                              ssh_exception=True)
        client = ParallelSSHClient([self.host],
                                   user='fakey', password='fakey',
                                   port=listen_port,
                                   pkey=RSAKey.generate(1024),
                                   )
        self.assertRaises(SSHException, client.run_command, self.fake_cmd)
        del client
        server.kill()
    
    def test_pssh_client_timeout(self):
        listen_socket = make_socket(self.host)
        listen_port = listen_socket.getsockname()[1]
        server_timeout=0.2
        client_timeout=server_timeout-0.1
        server = start_server(listen_socket,
                              timeout=server_timeout)
        client = ParallelSSHClient([self.host], port=listen_port,
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
        # chan_timeout = output[self.host]['channel'].gettimeout()
        # self.assertEqual(client_timeout, chan_timeout,
        #                  msg="Channel timeout %s does not match requested timeout %s" %(
        #                      chan_timeout, client_timeout,))
        del client
        server.kill()

    def test_pssh_client_exec_command_password(self):
        """Test password authentication. Embedded server accepts any password
        even empty string"""
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   password='')
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        self.assertTrue(self.host in output,
                        msg="No output for host")
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Expected exit code 0, got %s" % (
                            output[self.host]['exit_code'],))
        del client

    def test_pssh_client_long_running_command(self):
        expected_lines = 5
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        cmd = client.exec_command(self.long_cmd(expected_lines))[0]
        output = client.get_stdout(cmd, return_buffers=True)
        self.assertTrue(self.host in output, msg="Got no output for command")
        stdout = list(output[self.host]['stdout'])
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))
        del client

    def test_pssh_client_long_running_command_exit_codes(self):
        expected_lines = 5
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        output = client.run_command(self.long_cmd(expected_lines))
        self.assertTrue(self.host in output, msg="Got no output for command")
        self.assertTrue(not output[self.host]['exit_code'],
                        msg="Got exit code %s for still running cmd.." % (
                            output[self.host]['exit_code'],))
        self.assertFalse(client.finished(output))
        # Embedded server is also asynchronous and in the same thread
        # as our client so need to sleep for duration of server connection
        gevent.sleep(expected_lines)
        client.join(output)
        self.assertTrue(client.finished(output))
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Got non-zero exit code %s" % (
                            output[self.host]['exit_code'],))
        del client
    
    def test_pssh_client_retries(self):
        """Test connection error retries"""
        listen_socket = make_socket(self.host)
        listen_port = listen_socket.getsockname()[1]
        expected_num_tries = 2
        client = ParallelSSHClient([self.host], port=listen_port,
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
    
    def test_sftp_exceptions(self):
        self.server.kill()
        # Make socket with no server listening on it on separate ip
        host = '127.0.0.3'
        _socket = make_socket(host)
        port = _socket.getsockname()[1]
        client = ParallelSSHClient([self.host], port=port, num_retries=1)
        cmds = client.copy_file("test", "test")
        client.pool.join()
        for cmd in cmds:
            self.assertRaises(ConnectionErrorException, cmd.get)
    
    def test_pssh_copy_file(self):
        """Test parallel copy file"""
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filename = 'remote_test_dir', 'test_file_copy'
        remote_filename = os.path.sep.join([remote_test_dir, remote_filename])
        test_file = open(local_filename, 'w')
        test_file.writelines([test_file_data + os.linesep])
        test_file.close()
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        cmds = client.copy_file(local_filename, remote_filename)
        cmds[0].get()
        self.assertTrue(os.path.isdir(remote_test_dir),
                        msg="SFTP create remote directory failed")
        self.assertTrue(os.path.isfile(remote_filename),
                        msg="SFTP copy failed")
        for filepath in [local_filename, remote_filename]:
            os.unlink(filepath)
        shutil.rmtree(remote_test_dir)
        del client
    
    def test_pssh_client_directory(self):
        """Tests copying multiple directories with SSH client. Copy all the files from
        local directory to server, then make sure they are all present."""
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
        for path in [local_test_path, remote_test_path]:
            try:
                shutil.rmtree(path)
            except OSError:
                pass
        os.mkdir(local_test_path)
        remote_file_paths = []
        for i in range(0, 10):
            local_file_path_dir = os.path.join(local_test_path, 'dir_foo' + str(i))
            os.mkdir(local_file_path_dir)
            local_file_path = os.path.join(local_file_path_dir, 'foo' + str(i))
            remote_file_path = os.path.join(remote_test_path, 'dir_foo' + str(i), 'foo' + str(i))
            remote_file_paths.append(remote_file_path)
            test_file = open(local_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        cmds = client.copy_file(local_test_path, remote_test_path, recurse=True)
        for cmd in cmds:
            cmd.get()
        for path in remote_file_paths:
            self.assertTrue(os.path.isfile(path))
        shutil.rmtree(local_test_path)
        shutil.rmtree(remote_test_path)

    def test_pssh_client_copy_file_failure(self):
        """Test failure scenarios of file copy"""
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
        for path in [local_test_path, remote_test_path]:
            mask = int('0700') if sys.version_info <= (2,) else 0o700
            if os.path.isdir(path):
                os.chmod(path, mask)
            for root, dirs, files in os.walk(path):
                os.chmod(root, mask)
                for _path in files + dirs:
                    os.chmod(os.path.join(root, _path), mask)
            try:
                shutil.rmtree(path)
            except OSError:
                pass
        os.mkdir(local_test_path)
        os.mkdir(remote_test_path)
        local_file_path = os.path.join(local_test_path, 'test_file')
        remote_file_path = os.path.join(remote_test_path, 'test_file')
        test_file = open(local_file_path, 'w')
        test_file.write('testing\n')
        test_file.close()
        # Permission errors on writing into dir
        mask = 0111 if sys.version_info <= (2,) else 0o111
        os.chmod(remote_test_path, mask)
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        cmds = client.copy_file(local_test_path, remote_test_path, recurse=True)
        for cmd in cmds:
            try:
                cmd.get()
                raise Exception("Expected IOError exception, got none")
            except IOError:
                pass
        self.assertFalse(os.path.isfile(remote_file_path))
        # Create directory tree failure test
        local_file_path = os.path.join(local_test_path, 'test_file')
        remote_file_path = os.path.join(remote_test_path, 'test_dir', 'test_file')
        cmds = client.copy_file(local_file_path, remote_file_path, recurse=True)
        for cmd in cmds:
            try:
                cmd.get()
                raise Exception("Expected IOError exception on creating remote "
                                "directory, got none")
            except IOError:
                pass
        self.assertFalse(os.path.isfile(remote_file_path))
        mask = int('0600') if sys.version_info <= (2,) else 0o600
        os.chmod(remote_test_path, mask)
        for path in [local_test_path, remote_test_path]:
            shutil.rmtree(path)
    
    def test_pssh_copy_file_to_local(self):
        """Test parallel copy file to local host"""
        test_file_data = 'test'
        remote_filename = 'test_file'
        local_test_dir, local_filename = 'local_test_dir', 'test_file_copy'
        local_filename = os.path.sep.join([local_test_dir, local_filename])
        test_file = open(remote_filename, 'w')
        test_file.writelines([test_file_data + os.linesep])
        test_file.close()
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        cmds = client.copy_file_to_local(remote_filename, local_filename)
        cmds[0].get()
        local_filename += '_' + self.host
        self.assertTrue(os.path.isdir(local_test_dir),
                        msg="SFTP create local directory failed")
        self.assertTrue(os.path.isfile(local_filename),
                        msg="SFTP copy failed")
        for filepath in [remote_filename, local_filename]:
            os.unlink(filepath)
        shutil.rmtree(local_test_dir)
        del client
        server.join()

    def test_pssh_pool_size(self):
        """Test setting pool size to non default values"""
        hosts = ['host-%01d' % d for d in xrange(5)]
        pool_size = 2
        client = ParallelSSHClient(hosts, pool_size=pool_size)
        expected, actual = pool_size, client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))
        hosts = ['host-%01d' % d for d in xrange(15)]
        pool_size = 5
        client = ParallelSSHClient(hosts, pool_size=pool_size)
        expected, actual = client.pool_size, client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))
        hosts = ['host-%01d' % d for d in xrange(15)]
        pool_size = len(hosts)+5
        client = ParallelSSHClient(hosts, pool_size=pool_size)
        expected, actual = pool_size, client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))

    def test_pssh_hosts_more_than_pool_size(self):
        """Test we can successfully run on more hosts than our pool size and
        get logs for all hosts"""
        # Make a second server on the same port as the first one
        server2_socket = make_socket('127.0.0.2', port=self.listen_port)
        server2_port = server2_socket.getsockname()[1]
        server2 = start_server(server2_socket)
        hosts = [self.host, '127.0.0.2']
        client = ParallelSSHClient(hosts,
                                   port=self.listen_port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.fake_cmd)
        stdout = [list(output[k]['stdout']) for k in output]
        expected_stdout = [[self.fake_resp], [self.fake_resp]]
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        self.assertEqual(expected_stdout, stdout,
                         msg="Did not get expected output from all hosts. \
                         Got %s - expected %s" % (stdout, expected_stdout,))
        del client
        del server2
    
    def test_pssh_hosts_iterator_hosts_modification(self):
        """Test using iterator as host list and modifying host list in place"""
        server2_socket = make_socket('127.0.0.2', port=self.listen_port)
        server2_port = server2_socket.getsockname()[1]
        server2 = start_server(server2_socket)
        server3_socket = make_socket('127.0.0.3', port=self.listen_port)
        server3_port = server3_socket.getsockname()[1]
        server3 = start_server(server3_socket)
        hosts = [self.host, '127.0.0.2']
        client = ParallelSSHClient(iter(hosts),
                                   port=self.listen_port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.fake_cmd)
        stdout = [list(output[k]['stdout']) for k in output]
        expected_stdout = [[self.fake_resp], [self.fake_resp]]
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        # Run again without re-assigning host list, should do nothing
        output = client.run_command(self.fake_cmd)
        self.assertFalse(hosts[0] in output,
                         msg="Expected no host output, got %s" % (output,))
        self.assertFalse(output,
                         msg="Expected empty output, got %s" % (output,))
        # Re-assigning host list with new hosts should work
        hosts = ['127.0.0.2', '127.0.0.3']
        client.hosts = iter(hosts)
        output = client.run_command(self.fake_cmd)
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        self.assertTrue(hosts[1] in output,
                        msg="Did not get output for new host %s" % (hosts[1],))
        del client, server2, server3
    
    def test_ssh_proxy(self):
        """Test connecting to remote destination via SSH proxy
        client -> proxy -> destination
        Proxy SSH server accepts no commands and sends no responses, only
        proxies to destination. Destination accepts a command as usual."""
        proxy_server_socket = make_socket('127.0.0.2')
        proxy_server_port = proxy_server_socket.getsockname()[1]
        proxy_server = start_server(proxy_server_socket)
        gevent.sleep(2)
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   proxy_host='127.0.0.2',
                                   proxy_port=proxy_server_port
                                   )
        gevent.sleep(2)
        output = client.run_command(self.fake_cmd)
        stdout = list(output[self.host]['stdout'])
        expected_stdout = [self.fake_resp]
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" % 
                         (stdout,
                          expected_stdout,))
        self.server.kill()
        proxy_server.kill()

    def test_ssh_proxy_auth(self):
        """Test connecting to remote destination via SSH proxy
        client -> proxy -> destination
        Proxy SSH server accepts no commands and sends no responses, only
        proxies to destination. Destination accepts a command as usual."""
        proxy_server_socket = make_socket('127.0.0.2')
        proxy_server_port = proxy_server_socket.getsockname()[1]
        proxy_server = start_server(proxy_server_socket)
        proxy_user = 'proxy_user'
        proxy_password = 'fake'
        gevent.sleep(2)
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   proxy_host='127.0.0.2',
                                   proxy_port=proxy_server_port,
                                   proxy_user=proxy_user,
                                   proxy_password='fake',
                                   proxy_pkey=self.user_key,
                                   )
        gevent.sleep(2)
        output = client.run_command(self.fake_cmd)
        stdout = list(output[self.host]['stdout'])
        expected_stdout = [self.fake_resp]
        self.assertEqual(expected_stdout, stdout,
                         msg="Got unexpected stdout - %s, expected %s" % (
                             stdout, expected_stdout,))
        self.assertEqual(client.host_clients[self.host].proxy_user, proxy_user)
        self.assertEqual(client.host_clients[self.host].proxy_password, proxy_password)
        self.assertTrue(client.host_clients[self.host].proxy_pkey)
        self.server.kill()
        proxy_server.kill()

    def test_ssh_proxy_auth_fail(self):
        """Test failures while connecting via proxy"""
        listen_socket = make_socket(self.host)
        listen_port = listen_socket.getsockname()[1]
        self.server.kill()
        server = start_server(listen_socket,
                              fail_auth=True)
        proxy_server_socket = make_socket('127.0.0.2')
        proxy_server_port = proxy_server_socket.getsockname()[1]
        proxy_server = start_server(proxy_server_socket)
        proxy_user = 'proxy_user'
        proxy_password = 'fake'
        gevent.sleep(2)
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   proxy_host='127.0.0.2',
                                   proxy_port=proxy_server_port,
                                   proxy_user=proxy_user,
                                   proxy_password='fake',
                                   proxy_pkey=self.user_key,
                                   )
        gevent.sleep(2)
        self.assertRaises(AuthenticationException, client.run_command, self.fake_cmd)
        del client
        server.kill()
        proxy_server.kill()

    def test_bash_variable_substitution(self):
        """Test bash variables work correctly"""
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        command = """for i in 1 2 3; do echo $i; done"""
        output = list(client.run_command(command)[self.host]['stdout'])
        expected = ['1','2','3']
        self.assertEqual(output, expected,
                         msg="Unexpected output from bash variable substitution %s - should be %s" % (
                             output, expected,))
    
    def test_identical_host_output(self):
        """Test that we get output when running with duplicated hosts"""
        # Make socket with no server listening on it just for testing output
        _socket1, _socket2 = make_socket(self.host), make_socket(self.host)
        port = _socket1.getsockname()[1]
        hosts = [self.host, self.host, self.host]
        client = ParallelSSHClient(hosts, port=port,
                                   pkey=self.user_key)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertEqual(len(hosts), len(output.keys()),
                         msg="Host list contains %s identical hosts, only got output for %s" % (
                             len(hosts), len(output.keys())))
        del _socket1, _socket2
    
    def test_connection_error_exception(self):
        """Test that we get connection error exception in output with correct arguments"""
        self.server.kill()
        # Make socket with no server listening on it on separate ip
        host = '127.0.0.3'
        _socket = make_socket(host)
        port = _socket.getsockname()[1]
        hosts = [host]
        client = ParallelSSHClient(hosts, port=port,
                                   pkey=self.user_key)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertTrue('exception' in output[host],
                        msg="Got no exception for host %s - expected connection error" % (
                            host,))
        try:
            raise output[host]['exception']
        except ConnectionErrorException, ex:
            self.assertEqual(ex.args[1], host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected ConnectionErrorException")
        del _socket
    
    def test_authentication_exception(self):
        """Test that we get authentication exception in output with correct arguments"""
        self.server.kill()
        _socket = make_socket(self.host)
        port = _socket.getsockname()[1]
        server = start_server(_socket, fail_auth=True)
        hosts = [self.host]
        client = ParallelSSHClient(hosts, port=port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertTrue('exception' in output[self.host],
                        msg="Got no exception for host %s - expected connection error" % (
                            self.host,))
        try:
            raise output[self.host]['exception']
        except AuthenticationException, ex:
            self.assertEqual(ex.args[1], self.host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], self.host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected AuthenticationException")
        server.kill()
        del _socket
    
    def test_ssh_exception(self):
        """Test that we get ssh exception in output with correct arguments"""
        self.server.kill()
        host = '127.0.0.10'
        _socket = make_socket(host)
        port = _socket.getsockname()[1]
        server = start_server(_socket, ssh_exception=True)
        hosts = [host]
        client = ParallelSSHClient(hosts, port=port,
                                   user='fakey', password='fakey',
                                   pkey=RSAKey.generate(1024))
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        gevent.sleep(1)
        client.pool.join()
        self.assertTrue('exception' in output[host],
                        msg="Got no exception for host %s - expected connection error" % (
                            host,))
        try:
            raise output[host]['exception']
        except SSHException, ex:
            self.assertEqual(ex.args[1], host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected SSHException")
        server.kill()
        del _socket
    
    def test_multiple_single_quotes_in_cmd(self):
        """Test that we can run a command with multiple single quotes"""
        output = self.client.run_command("echo 'me' 'and me'")
        stdout = list(output[self.host]['stdout'])
        expected = 'me and me'
        self.assertTrue(len(stdout)==1,
                        msg="Got incorrect number of lines in output - %s" % (stdout,))
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Error executing cmd with multiple single quotes - %s" % (
                            stdout,))
        self.assertEqual(expected, stdout[0],
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout[0],))
    
    def test_backtics_in_cmd(self):
        """Test running command with backtics in it"""
        output = self.client.run_command("out=`ls` && echo $out")
        self.client.join(output)
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Error executing cmd with backtics - error code %s" % (
                            output[self.host]['exit_code'],))
    
    def test_multiple_shell_commands(self):
        """Test running multiple shell commands in one go"""
        output = self.client.run_command("echo me; echo and; echo me")
        stdout = list(output[self.host]['stdout'])
        expected = ["me", "and", "me"]
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Error executing multiple shell cmds - error code %s" % (
                            output[self.host]['exit_code'],))
        self.assertEqual(expected, stdout,
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout,))
    
    def test_escaped_quotes(self):
        """Test escaped quotes in shell variable are handled correctly"""
        output = self.client.run_command('t="--flags=\\"this\\""; echo $t')
        stdout = list(output[self.host]['stdout'])
        expected = ['--flags="this"']
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Error executing multiple shell cmds - error code %s" % (
                            output[self.host]['exit_code'],))
        self.assertEqual(expected, stdout,
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout,))

    def test_host_config(self):
        """Test per-host configuration functionality of ParallelSSHClient"""
        hosts = ['127.0.0.%01d' % n for n in xrange(1,3)]
        host_config = dict.fromkeys(hosts)
        servers = []
        user = 'overriden_user'
        password = 'overriden_pass'
        for host in hosts:
            _socket = make_socket(host)
            port = _socket.getsockname()[1]
            host_config[host] = {}
            host_config[host]['port'] = port
            host_config[host]['user'] = user
            host_config[host]['password'] = password
            server = start_server(_socket, fail_auth=hosts.index(host))
            servers.append((server, port))
        pkey_data = load_private_key(PKEY_FILENAME)
        host_config[hosts[0]]['private_key'] = pkey_data
        client = ParallelSSHClient(hosts, host_config=host_config)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.join(output)
        for host in hosts:
            self.assertTrue(host in output)
        try:
            raise output[hosts[1]]['exception']
        except AuthenticationException, ex:
            pass
        else:
            raise AssertionError("Expected AutnenticationException on host %s",
                                 hosts[0])
        self.assertFalse(output[hosts[1]]['exit_code'],
                         msg="Execution failed on host %s" % (hosts[1],))
        self.assertTrue(client.host_clients[hosts[0]].user == user,
                        msg="Host config user override failed")
        self.assertTrue(client.host_clients[hosts[0]].password == password,
                        msg="Host config password override failed")
        self.assertTrue(client.host_clients[hosts[0]].pkey == pkey_data,
                        msg="Host config pkey override failed")
        for (server, _) in servers:
            server.kill()

    def test_pssh_client_override_allow_agent_authentication(self):
        """Test running command with allow_agent set to False"""
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key, allow_agent=False)
        output = client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        exit_code = output[self.host]['exit_code']
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

    def test_get_exit_codes_bad_output(self):
        self.assertFalse(self.client.get_exit_codes({}))
        self.assertFalse(self.client.get_exit_code({}))

    def test_per_host_tuple_args(self):
        server2_socket = make_socket('127.0.0.2', port=self.listen_port)
        server2_port = server2_socket.getsockname()[1]
        server2 = start_server(server2_socket)
        server3_socket = make_socket('127.0.0.3', port=self.listen_port)
        server3_port = server3_socket.getsockname()[1]
        server3 = start_server(server3_socket)
        hosts = [self.host, '127.0.0.2', '127.0.0.3']
        host_args = ('arg1', 'arg2', 'arg3')
        cmd = 'echo %s'
        client = ParallelSSHClient(hosts, port=self.listen_port,
                                   pkey=self.user_key)
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = [host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host]['exit_code'] == 0)
        host_args = (('arg1', 'arg2'), ('arg3', 'arg4'), ('arg5', 'arg6'),)
        cmd = 'echo %s %s'
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%s %s" % host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host]['exit_code'] == 0)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])

    def test_per_host_dict_args(self):
        server2_socket = make_socket('127.0.0.2', port=self.listen_port)
        server2_port = server2_socket.getsockname()[1]
        server2 = start_server(server2_socket)
        server3_socket = make_socket('127.0.0.3', port=self.listen_port)
        server3_port = server3_socket.getsockname()[1]
        server3 = start_server(server3_socket)
        hosts = [self.host, '127.0.0.2', '127.0.0.3']
        hosts_gen = (h for h in hosts)
        host_args = [dict(zip(('host_arg1', 'host_arg2',),
                              ('arg1-%s' % (i,), 'arg2-%s' % (i,),)))
                     for i, _ in enumerate(hosts)]
        cmd = 'echo %(host_arg1)s %(host_arg2)s'
        client = ParallelSSHClient(hosts, port=self.listen_port,
                                   pkey=self.user_key)
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%(host_arg1)s %(host_arg2)s" % host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host]['exit_code'] == 0)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])
        # Host list generator should work also
        client.hosts = hosts_gen
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%(host_arg1)s %(host_arg2)s" % host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host]['exit_code'] == 0)
        client.hosts = (h for h in hosts)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])

if __name__ == '__main__':
    unittest.main()
