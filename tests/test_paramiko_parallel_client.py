# -*- coding: utf-8 -*-
#
# This file is part of parallel-ssh.
#
# Copyright (C) 2015 Panos Kittenis
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

"""Unittests for :mod:`pssh.ParallelSSHClient` class"""


import unittest
import random
import logging
import os
import warnings
import shutil
import sys
from socket import timeout as socket_timeout
from platform import python_version

from gevent import sleep
from pssh.pssh_client import ParallelSSHClient, logger as pssh_logger
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SSHException, \
    HostArgumentException
from pssh.utils import load_private_key
from .embedded_server.embedded_server import start_server, make_socket, \
     logger as server_logger, paramiko_logger, start_server_from_ip
from pssh.agent import SSHAgent
from paramiko import RSAKey

PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key'])
USER_KEY = RSAKey.from_private_key_file(PKEY_FILENAME)

server_logger.setLevel(logging.DEBUG)
pssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


try:
    xrange
except NameError:
    xrange = range


class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'echo "me"'
        self.fake_resp = 'me'
        self.long_cmd = lambda lines: 'for (( i=0; i<%s; i+=1 )) do echo $i; sleep 1; done' % (lines,)
        self.user_key = USER_KEY
        self.host = '127.0.0.1'
        self.server_sock = make_socket(self.host)
        self.listen_port = self.server_sock.getsockname()[1]
        self.server = start_server(self.server_sock)
        self.agent = SSHAgent()
        self.agent.add_key(USER_KEY)
        self.client = ParallelSSHClient([self.host], port=self.listen_port,
                                        pkey=self.user_key,
                                        agent=self.agent)

    def make_random_port(self, host=None):
        host = self.host if not host else host
        listen_socket = make_socket(host)
        listen_port = listen_socket.getsockname()[1]
        del listen_socket
        return listen_port

    def tearDown(self):
        del self.client
        self.server.kill()
        del self.agent

    def test_client_join_consume_output(self):
        output = self.client.run_command(self.fake_cmd)
        expected_exit_code = 0
        self.client.join(output, consume_output=True)
        exit_code = output[self.host].exit_code
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        self.assertTrue(len(stdout) == 0)
        self.assertTrue(len(stderr) == 0)
        self.assertEqual(expected_exit_code, exit_code)

    def test_client_join_stdout(self):
        output = self.client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        self.client.join(output)
        exit_code = output[self.host].exit_code
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

    def test_pssh_client_no_stdout_non_zero_exit_code_immediate_exit(self):
        output = self.client.run_command('exit 1')
        expected_exit_code = 1
        self.client.join(output)
        exit_code = output[self.host].exit_code
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))

    def test_pssh_client_run_command_get_output(self):
        output = self.client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        exit_code = output[self.host].exit_code
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
        out = self.client.run_command(self.fake_cmd)
        cmds = [cmd for host in out for cmd in [out[host]['cmd']]]
        output = {}
        for cmd in cmds:
            self.client.get_output(cmd, output)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        stdout = list(output[self.host].stdout)
        stderr = list(output[self.host].stderr)
        exit_code = output[self.host].exit_code
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

    def test_pssh_client_run_long_command(self):
        expected_lines = 5
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.assertTrue(self.host in output, msg="Got no output for command")
        stdout = list(output[self.host]['stdout'])
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))

    def test_pssh_client_auth_failure(self):
        server, listen_port = start_server_from_ip(self.host,
                                                   fail_auth=True)
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        self.assertRaises(
            AuthenticationException, client.run_command, self.fake_cmd)
        del client
        server.kill()

    def test_pssh_client_hosts_list_part_failure(self):
        """Test getting output for remainder of host list in the case where one
        host in the host list has a failure"""
        server2, _ = start_server_from_ip('127.0.0.2', port=self.listen_port,
                                          fail_auth=True)
        hosts = [self.host, '127.0.0.2']
        client = ParallelSSHClient(hosts,
                                   port=self.listen_port,
                                   pkey=self.user_key,
                                   agent=self.agent)
        output = client.run_command('sleep 1; echo me',
                                    stop_on_errors=False)
        self.assertFalse(client.finished(output))
        client.join(output, consume_output=True)
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
        server, listen_port = start_server_from_ip(self.host,
                                                   ssh_exception=True)
        client = ParallelSSHClient([self.host],
                                   user='fakey', password='fakey',
                                   port=listen_port,
                                   pkey=RSAKey.generate(1024),
                                   num_retries=1,
                                   )
        self.assertRaises(SSHException, client.run_command, self.fake_cmd)
        del client
        server.kill()

    def test_pssh_client_timeout(self):
        server_timeout=0.2
        client_timeout=server_timeout-0.1
        server, listen_port = start_server_from_ip(self.host,
                                                   timeout=server_timeout)
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   timeout=client_timeout,
                                   num_retries=1)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        # Handle exception
        try:
            sleep(server_timeout+0.2)
            client.join(output)
            if not server.exception:
                raise Exception(
                    "Expected gevent.Timeout from socket timeout, got none")
        finally:
            del client
            server.kill()

    def test_pssh_client_run_command_password(self):
        """Test password authentication. Embedded server accepts any password
        even empty string"""
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   password='')
        output = client.run_command(self.fake_cmd)
        stdout = list(output[self.host]['stdout'])
        self.assertTrue(self.host in output,
                        msg="No output for host")
        self.assertTrue(output[self.host].exit_code == 0,
                        msg="Expected exit code 0, got %s" % (
                            output[self.host].exit_code,))
        self.assertEqual(stdout, [self.fake_resp])

    def test_pssh_client_long_running_command_exit_codes(self):
        expected_lines = 5
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.assertTrue(self.host in output, msg="Got no output for command")
        self.assertTrue(not output[self.host].exit_code,
                        msg="Got exit code %s for still running cmd.." % (
                            output[self.host].exit_code,))
        self.assertFalse(self.client.finished(output))
        # Embedded server is also asynchronous and in the same thread
        # as our client so need to sleep for duration of server connection
        self.client.join(output, consume_output=True)
        sleep(expected_lines)
        self.assertTrue(self.client.finished(output))
        self.assertEqual(output[self.host].exit_code, 0,
                        msg="Got non-zero exit code %s" % (
                            output[self.host].exit_code,))

    def test_pssh_client_retries(self):
        """Test connection error retries"""
        listen_port = self.make_random_port()
        expected_num_tries = 2
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   num_retries=expected_num_tries)
        self.assertRaises(ConnectionErrorException, client.run_command, 'blah')
        try:
            client.run_command('blah')
        except ConnectionErrorException as ex:
            num_tries = ex.args[-1:][0]
            self.assertEqual(expected_num_tries, num_tries,
                             msg="Got unexpected number of retries %s - "
                             "expected %s" % (num_tries, expected_num_tries,))
        else:
            raise Exception('No ConnectionErrorException')

    def test_sftp_exceptions(self):
        # Port with no server listening on it on separate ip
        host = '127.0.0.3'
        port = self.make_random_port(host=host)
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
        mask = int('0111') if sys.version_info <= (2,) else 0o111
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

    def test_pssh_copy_remote_file(self):
        """Test parallel copy file to local host"""
        test_file_data = 'test'
        local_test_path = 'directory_test_local_remote_copied'
        remote_test_path = 'directory_test_remote_copy'
        local_copied_dir = '_'.join([local_test_path, self.host])
        new_local_copied_dir = '.'.join([local_test_path, self.host])
        for path in [local_test_path, remote_test_path, local_copied_dir,
                     new_local_copied_dir]:
            try:
                shutil.rmtree(path)
            except OSError:
                try:
                    os.unlink(path)
                except Exception:
                    pass
                pass
        os.mkdir(remote_test_path)
        local_file_paths = []
        for i in range(0, 10):
            remote_file_path_dir = os.path.join(remote_test_path, 'dir_foo' + str(i))
            os.mkdir(remote_file_path_dir)
            remote_file_path = os.path.join(remote_file_path_dir, 'foo' + str(i))
            local_file_path = os.path.join(local_copied_dir, 'dir_foo' + str(i), 'foo' + str(i))
            local_file_paths.append(local_file_path)
            test_file = open(remote_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key)
        cmds = client.copy_remote_file(remote_test_path, local_test_path)
        for cmd in cmds:
            self.assertRaises(ValueError, cmd.get)
        cmds = client.copy_remote_file(remote_test_path, local_test_path,
                                       recurse=True)
        for cmd in cmds:
            cmd.get()
        try:
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        except Exception:
            shutil.rmtree(remote_test_path)
        finally:
            shutil.rmtree(local_copied_dir)
        cmds = client.copy_remote_file(remote_test_path, local_test_path,
                                       suffix_separator='.', recurse=True)
        for cmd in cmds:
            cmd.get()
        new_local_copied_dir = '.'.join([local_test_path, self.host])
        try:
            for path in local_file_paths:
                path = path.replace(local_copied_dir, new_local_copied_dir)
                self.assertTrue(os.path.isfile(path))
        finally:
            shutil.rmtree(new_local_copied_dir)
            shutil.rmtree(remote_test_path)

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
        host2 = '127.0.0.2'
        server2, _ = start_server_from_ip(host2, port=self.listen_port)
        hosts = [self.host, host2]
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
        server2.kill()

    def test_pssh_hosts_iterator_hosts_modification(self):
        """Test using iterator as host list and modifying host list in place"""
        host2, host3 = '127.0.0.2', '127.0.0.3'
        server2, _ = start_server_from_ip(host2, port=self.listen_port)
        server3, _ = start_server_from_ip(host3, port=self.listen_port)
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
        del client
        server2.kill()
        server3.kill()

    @unittest.skip('flaky af')
    def test_ssh_proxy(self):
        """Test connecting to remote destination via SSH proxy
        client -> proxy -> destination
        Proxy SSH server accepts no commands and sends no responses, only
        proxies to destination. Destination accepts a command as usual."""
        del self.client
        self.client = None
        self.server.kill()
        server, _ = start_server_from_ip(self.host, port=self.listen_port)
        proxy_host = '127.0.0.2'
        proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   proxy_host=proxy_host,
                                   proxy_port=proxy_server_port,
                                   )
        try:
            output = client.run_command(self.fake_cmd)
            stdout = list(output[self.host]['stdout'])
            expected_stdout = [self.fake_resp]
            self.assertEqual(expected_stdout, stdout,
                             msg="Got unexpected stdout - %s, expected %s" % 
                             (stdout,
                              expected_stdout,))
        finally:
            del client
            server.kill()
            proxy_server.kill()

    @unittest.skip('flaky af')
    def test_ssh_proxy_target_host_failure(self):
        del self.client
        self.client = None
        self.server.kill()
        proxy_host = '127.0.0.2'
        proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   proxy_host=proxy_host,
                                   proxy_port=proxy_server_port,
                                   )
        try:
            self.assertRaises(
                ConnectionErrorException, client.run_command, self.fake_cmd)
        finally:
            del client
            proxy_server.kill()

    @unittest.skip('flaky af')
    def test_ssh_proxy_auth(self):
        """Test connecting to remote destination via SSH proxy
        client -> proxy -> destination
        Proxy SSH server accepts no commands and sends no responses, only
        proxies to destination. Destination accepts a command as usual."""
        host2 = '127.0.0.2'
        proxy_server, proxy_server_port = start_server_from_ip(host2)
        proxy_user = 'proxy_user'
        proxy_password = 'fake'
        client = ParallelSSHClient([self.host], port=self.listen_port,
                                   pkey=self.user_key,
                                   proxy_host=host2,
                                   proxy_port=proxy_server_port,
                                   proxy_user=proxy_user,
                                   proxy_password='fake',
                                   proxy_pkey=self.user_key,
                                   num_retries=1,
                                   )
        expected_stdout = [self.fake_resp]
        try:
            output = client.run_command(self.fake_cmd)
            stdout = list(output[self.host]['stdout'])
            self.assertEqual(expected_stdout, stdout,
                            msg="Got unexpected stdout - %s, expected %s" % (
                                stdout, expected_stdout,))
            self.assertEqual(client.host_clients[self.host].proxy_user,
                             proxy_user)
            self.assertEqual(client.host_clients[self.host].proxy_password,
                             proxy_password)
            self.assertTrue(client.host_clients[self.host].proxy_pkey)
        finally:
            del client
            proxy_server.kill()

    @unittest.skip('flaky af')
    def test_ssh_proxy_auth_fail(self):
        """Test failures while connecting via proxy"""
        proxy_host = '127.0.0.2'
        server, listen_port = start_server_from_ip(self.host, fail_auth=True)
        proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
        proxy_user = 'proxy_user'
        proxy_password = 'fake'
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   proxy_host='127.0.0.2',
                                   proxy_port=proxy_server_port,
                                   proxy_user=proxy_user,
                                   proxy_password='fake',
                                   proxy_pkey=self.user_key,
                                   num_retries=1,
                                   )
        try:
            self.assertRaises(
                AuthenticationException, client.run_command, self.fake_cmd)
        finally:
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
        # Make port with no server listening on it just for testing output
        port = self.make_random_port()
        hosts = [self.host, self.host, self.host]
        client = ParallelSSHClient(hosts, port=port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertEqual(len(hosts), len(output.keys()),
                         msg="Host list contains %s identical hosts, only got output for %s" % (
                             len(hosts), len(output.keys())))

    def test_connection_error_exception(self):
        """Test that we get connection error exception in output with correct arguments"""
        # Make port with no server listening on it on separate ip
        host = '127.0.0.3'
        port = self.make_random_port(host=host)
        hosts = [host]
        client = ParallelSSHClient(hosts, port=port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertTrue('exception' in output[host],
                        msg="Got no exception for host %s - expected connection error" % (
                            host,))
        try:
            raise output[host]['exception']
        except ConnectionErrorException as ex:
            self.assertEqual(ex.args[1], host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected ConnectionErrorException")

    def test_authentication_exception(self):
        """Test that we get authentication exception in output with correct arguments"""
        server, port = start_server_from_ip(self.host, fail_auth=True)
        hosts = [self.host]
        client = ParallelSSHClient(hosts, port=port,
                                   pkey=self.user_key,
                                   agent=self.agent,
                                   num_retries=1)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertTrue('exception' in output[self.host],
                        msg="Got no exception for host %s - expected connection error" % (
                            self.host,))
        try:
            raise output[self.host]['exception']
        except AuthenticationException as ex:
            self.assertEqual(ex.args[1], self.host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], self.host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected AuthenticationException")
        server.kill()

    def test_ssh_exception(self):
        """Test that we get ssh exception in output with correct arguments"""
        host = '127.0.0.10'
        server, port = start_server_from_ip(host, ssh_exception=True)
        hosts = [host]
        client = ParallelSSHClient(hosts, port=port,
                                   user='fakey', password='fakey',
                                   pkey=RSAKey.generate(1024),
                                   num_retries=1)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.pool.join()
        self.assertTrue('exception' in output[host],
                        msg="Got no exception for host %s - expected connection error" % (
                            host,))
        try:
            raise output[host]['exception']
        except SSHException as ex:
            self.assertEqual(ex.args[1], host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected SSHException")
        server.kill()

    def test_multiple_single_quotes_in_cmd(self):
        """Test that we can run a command with multiple single quotes"""
        output = self.client.run_command("echo 'me' 'and me'")
        stdout = list(output[self.host]['stdout'])
        expected = 'me and me'
        self.assertTrue(len(stdout)==1,
                        msg="Got incorrect number of lines in output - %s" % (stdout,))
        self.assertTrue(output[self.host].exit_code == 0,
                        msg="Error executing cmd with multiple single quotes - %s" % (
                            stdout,))
        self.assertEqual(expected, stdout[0],
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout[0],))

    def test_backtics_in_cmd(self):
        """Test running command with backtics in it"""
        output = self.client.run_command("out=`ls` && echo $out")
        self.client.join(output)
        self.assertTrue(output[self.host].exit_code == 0,
                        msg="Error executing cmd with backtics - error code %s" % (
                            output[self.host].exit_code,))

    def test_multiple_shell_commands(self):
        """Test running multiple shell commands in one go"""
        output = self.client.run_command("echo me; echo and; echo me")
        stdout = list(output[self.host]['stdout'])
        expected = ["me", "and", "me"]
        self.assertTrue(output[self.host].exit_code == 0,
                        msg="Error executing multiple shell cmds - error code %s" % (
                            output[self.host].exit_code,))
        self.assertEqual(expected, stdout,
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout,))

    def test_escaped_quotes(self):
        """Test escaped quotes in shell variable are handled correctly"""
        output = self.client.run_command('t="--flags=\\"this\\""; echo $t')
        stdout = list(output[self.host]['stdout'])
        expected = ['--flags="this"']
        self.assertTrue(output[self.host].exit_code == 0,
                        msg="Error executing multiple shell cmds - error code %s" % (
                            output[self.host].exit_code,))
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
            server, port = start_server_from_ip(host, fail_auth=hosts.index(host))
            host_config[host] = {}
            host_config[host]['port'] = port
            host_config[host]['user'] = user
            host_config[host]['password'] = password
            servers.append(server)
        pkey_data = load_private_key(PKEY_FILENAME)
        host_config[hosts[0]]['private_key'] = pkey_data
        client = ParallelSSHClient(hosts, host_config=host_config)
        output = client.run_command(self.fake_cmd, stop_on_errors=False)
        client.join(output)
        for host in hosts:
            self.assertTrue(host in output)
        try:
            raise output[hosts[1]]['exception']
        except AuthenticationException as ex:
            pass
        else:
            raise AssertionError("Expected AutnenticationException on host %s",
                                 hosts[0])
        self.assertFalse(output[hosts[1]].exit_code,
                         msg="Execution failed on host %s" % (hosts[1],))
        self.assertTrue(client.host_clients[hosts[0]].user == user,
                        msg="Host config user override failed")
        self.assertTrue(client.host_clients[hosts[0]].password == password,
                        msg="Host config password override failed")
        self.assertTrue(client.host_clients[hosts[0]].pkey == pkey_data,
                        msg="Host config pkey override failed")
        for server in servers:
            server.kill()

    def test_pssh_client_override_allow_agent_authentication(self):
        """Test running command with allow_agent set to False"""
        output = self.client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        exit_code = output[self.host].exit_code
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

    def test_get_exit_codes_bad_output(self):
        self.assertFalse(self.client.get_exit_codes({}))
        self.assertFalse(self.client.get_exit_code({}))

    @unittest.skip("Constantly hangs")
    def test_per_host_tuple_args(self):
        host2, host3 = '127.0.0.2', '127.0.0.3'
        server2, _ = start_server_from_ip(host2, port=self.listen_port)
        server3, _ = start_server_from_ip(host3, port=self.listen_port)
        hosts = [self.host, host2, host3]
        host_args = ('arg1', 'arg2', 'arg3')
        cmd = 'echo %s'
        client = ParallelSSHClient(hosts, port=self.listen_port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = [host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host].exit_code == 0)
        host_args = (('arg1', 'arg2'), ('arg3', 'arg4'), ('arg5', 'arg6'),)
        cmd = 'echo %s %s'
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%s %s" % host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host].exit_code == 0)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])
        # Invalid number of args
        host_args = (('arg1', ),)
        self.assertRaises(
            TypeError, client.run_command, cmd, host_args=host_args)
        for server in [server2, server3]:
            server.kill()

    def test_per_host_dict_args(self):
        host2, host3 = '127.0.0.2', '127.0.0.3'
        server2, _ = start_server_from_ip(host2, port=self.listen_port)
        server3, _ = start_server_from_ip(host3, port=self.listen_port)
        hosts = [self.host, host2, host3]
        hosts_gen = (h for h in hosts)
        host_args = [dict(zip(('host_arg1', 'host_arg2',),
                              ('arg1-%s' % (i,), 'arg2-%s' % (i,),)))
                     for i, _ in enumerate(hosts)]
        cmd = 'echo %(host_arg1)s %(host_arg2)s'
        client = ParallelSSHClient(hosts, port=self.listen_port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%(host_arg1)s %(host_arg2)s" % host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host].exit_code == 0)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])
        # Host list generator should work also
        client.hosts = hosts_gen
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%(host_arg1)s %(host_arg2)s" % host_args[i]]
            stdout = list(output[host]['stdout'])
            self.assertEqual(expected, stdout)
            self.assertTrue(output[host].exit_code == 0)
        client.hosts = (h for h in hosts)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])
        client.hosts = hosts

    def test_per_host_dict_args_invalid(self):
        cmd = 'echo %(host_arg1)s %(host_arg2)s'
        # Invalid number of host args
        host_args = [{'host_arg1': 'arg1'}]
        self.assertRaises(
            KeyError, self.client.run_command, cmd, host_args=host_args)

    def test_ssh_client_utf_encoding(self):
        """Test that unicode output works"""
        expected = [u'é']
        cmd = u"echo 'é'"
        output = self.client.run_command(cmd)
        stdout = list(output[self.host]['stdout'])
        self.assertEqual(expected, stdout,
                         msg="Got unexpected unicode output %s - expected %s" % (
                             stdout, expected,))
        utf16_server, server_port = start_server_from_ip(
            self.host, encoding='utf-16')
        client = ParallelSSHClient([self.host], port=server_port,
                                   pkey=self.user_key)
        # File is already set to utf-8, cannot use utf-16 only representations
        # Using ascii characters decoded as utf-16 on py2
        # and utf-8 encoded ascii decoded to utf-16 on py3
        output = client.run_command(self.fake_cmd, encoding='utf-16')
        stdout = list(output[self.host]['stdout'])
        if isinstance(self.fake_resp, bytes):
            self.assertEqual([self.fake_resp.decode('utf-16')], stdout)
        else:
            self.assertEqual([self.fake_resp.encode('utf-8').decode('utf-16')],
                             stdout)

    def test_pty(self):
        cmd = "exit 0"
        output = self.client.run_command(cmd, use_pty=False)
        self.client.join(output)
        stdout = list(output[self.host]['stdout'])
        exit_code = output[self.host].exit_code
        expected = []
        self.assertEqual(expected, stdout)
        self.assertTrue(exit_code == 0)

    def test_channel_timeout(self):
        cmd = "sleep 2; echo me"
        self.client = ParallelSSHClient([self.host], port=self.listen_port,
                                        pkey=self.user_key, channel_timeout=.1)
        output = self.client.run_command(cmd)
        self.assertRaises(socket_timeout, list, output[self.host]['stdout'])

    def test_output_attributes(self):
        output = self.client.run_command(self.fake_cmd)
        expected_exit_code = 0
        expected_stdout = [self.fake_resp]
        expected_stderr = []
        self.client.join(output)
        exit_code = output[self.host].exit_code
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        host_output = output[self.host]
        self.assertEqual(expected_exit_code, host_output.exit_code)
        self.assertEqual(expected_exit_code, host_output.exit_code)
        self.assertEqual(host_output['cmd'], host_output.cmd)
        self.assertEqual(host_output['exception'], host_output.exception)
        self.assertEqual(host_output['stdout'], host_output.stdout)
        self.assertEqual(host_output['stderr'], host_output.stderr)
        self.assertEqual(host_output['stdin'], host_output.stdin)
        self.assertEqual(host_output['channel'], host_output.channel)
        self.assertEqual(host_output['host'], host_output.host)
        self.assertTrue(hasattr(output[self.host], 'host'))
        self.assertTrue(hasattr(output[self.host], 'cmd'))
        self.assertTrue(hasattr(output[self.host], 'channel'))
        self.assertTrue(hasattr(output[self.host], 'stdout'))
        self.assertTrue(hasattr(output[self.host], 'stderr'))
        self.assertTrue(hasattr(output[self.host], 'stdin'))
        self.assertTrue(hasattr(output[self.host], 'exception'))
        self.assertTrue(hasattr(output[self.host], 'exit_code'))

    @unittest.skip('produces false failures')
    def test_run_command_user_sudo(self):
        user = 'cmd_user'
        output = self.client.run_command('some cmd', user=user,
                                         use_pty=False)
        self.client.join(output)
        stderr = list(output[self.host].stderr)
        self.assertTrue(len(stderr) > 0)
        self.assertTrue(output[self.host].exit_code == 1)

    def test_run_command_shell(self):
        output = self.client.run_command(self.fake_cmd, shell="bash -c")
        self.client.join(output)
        stdout = list(output[self.host].stdout)
        self.assertEqual(stdout, [self.fake_resp])

    def test_run_command_no_shell(self):
        output = self.client.run_command('id', use_shell=False)
        self.client.join(output)
        stdout = list(output[self.host].stdout)
        self.assertTrue(len(stdout) > 0)
        self.assertTrue(output[self.host].exit_code == 0)

    def test_extra_paramiko_args(self):
        output = self.client.run_command('id', gss_auth=True, gss_kex=True,
                                         gss_host='gss_host')
        trans = self.client.host_clients[self.host].client.get_transport()
        self.assertEqual(trans.gss_host, 'gss_host')

    @unittest.skip('flaky af')
    def test_proxy_remote_host_failure_timeout(self):
        """Test that timeout setting is passed on to proxy to be used for the
        proxy->remote host connection timeout
        """
        self.server.kill()
        server_timeout=0.2
        client_timeout=server_timeout-0.1
        server, listen_port = start_server_from_ip(self.host,
                                                   timeout=server_timeout)
        proxy_host = '127.0.0.2'
        proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
        proxy_user = 'proxy_user'
        proxy_password = 'fake'
        client = ParallelSSHClient([self.host], port=listen_port,
                                   pkey=self.user_key,
                                   proxy_host='127.0.0.2',
                                   proxy_port=proxy_server_port,
                                   proxy_user=proxy_user,
                                   proxy_password='fake',
                                   proxy_pkey=self.user_key,
                                   num_retries=1,
                                   timeout=client_timeout,
                                   )
        try:
            self.assertRaises(
                ConnectionErrorException, client.run_command, self.fake_cmd)
        finally:
            del client
            server.kill()
            proxy_server.kill()

    def test_openssh_config(self):
        self.server.kill()
        ssh_config = os.path.expanduser('~/.ssh/config')
        mode = '0700' if python_version() < '3' else 0o700
        if os.path.isfile(ssh_config):
            shutil.move(ssh_config, '.')
        elif not os.path.isdir(os.path.expanduser('~/.ssh')):
            os.mkdir(os.path.expanduser('~/.ssh'), mode=mode)
        config_file = open(ssh_config, 'w')
        _host = "127.0.0.2"
        _user = "config_user"
        _server, _port = start_server_from_ip(_host)
        content = [("""Host %s\n""" % (self.host,)),
                   ("""  HostName %s\n""" % (_host,)),
                   ("""  User %s\n""" % (_user,)),
                   ("""  Port %s\n""" % (_port,)),
                   ("""  IdentityFile %s\n""" % (PKEY_FILENAME,)),
        ]
        config_file.writelines(content)
        config_file.close()
        try:
            client = ParallelSSHClient([self.host],
                                       num_retries=1)
            output = client.run_command(self.fake_cmd)
            self.assertTrue(self.host in output)
            output = list(output[self.host].stdout)
            expected = [self.fake_resp]
            self.assertEqual(output, expected)
        except Exception:
            raise
        finally:
            os.unlink(ssh_config)
            if os.path.isfile('config'):
                shutil.move('config', os.path.expanduser('~/.ssh/'))


if __name__ == '__main__':
    unittest.main()
