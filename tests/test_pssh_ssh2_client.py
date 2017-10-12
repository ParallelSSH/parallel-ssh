#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import print_function

import unittest
import pwd
import logging
import os
import shutil
import sys
import string
from socket import timeout as socket_timeout
from sys import version_info
import random
import time


import gevent
from pssh.pssh2_client import ParallelSSHClient, logger as pssh_logger
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError

from .embedded_server.embedded_server import make_socket
from .embedded_server.openssh import OpenSSHServer
from .base_ssh2_test import SSH2TestCase, PKEY_FILENAME, PUB_FILE
# from pssh.utils import load_private_key
# from pssh.agent import SSHAgent


pssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class ParallelSSHClientTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.server = OpenSSHServer()
        cls.server.start_server()
        cls.host = '127.0.0.1'
        cls.port = 2222
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.user = pwd.getpwuid(os.geteuid()).pw_name
        cls.client = ParallelSSHClient([cls.host],
                                       pkey=PKEY_FILENAME,
                                       port=cls.port,
                                       num_retries=1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        del cls.server

    def setUp(self):
        self.long_cmd = lambda lines: 'for (( i=0; i<%s; i+=1 )) do echo $i; sleep 1; done' % (lines,)

    def make_random_port(self, host=None):
        host = self.host if not host else host
        listen_socket = make_socket(host)
        listen_port = listen_socket.getsockname()[1]
        del listen_socket
        return listen_port

    def test_client_join_consume_output(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        self.client.join(output, consume_output=True)
        exit_code = output[self.host].exit_code
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        self.assertTrue(len(stdout) == 0)
        self.assertTrue(len(stderr) == 0)
        self.assertEqual(expected_exit_code, exit_code)
        output = self.client.run_command('echo "me" >&2', use_pty=False)
        self.client.join(output, consume_output=True)
        exit_code = output[self.host].exit_code
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        self.assertTrue(len(stdout) == 0)
        self.assertTrue(len(stderr) == 0)
        self.assertEqual(expected_exit_code, exit_code)

    def test_client_join_stdout(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
        expected_stderr = []
        self.client.join(output)
        exit_code = output[self.host]['exit_code']
        stdout = list(output[self.host].stdout)
        stderr = list(output[self.host].stderr)
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

    def test_get_last_output(self):
        host = '127.0.0.9'
        server = OpenSSHServer(listen_ip=host, port=self.port)
        server.start_server()
        hosts = [self.host, host]
        client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key)
        self.assertTrue(client.cmds is None)
        self.assertTrue(client.get_last_output() is None)
        client.run_command(self.cmd)
        self.assertTrue(client.cmds is not None)
        self.assertEqual(len(client.cmds), len(hosts))
        output = client.get_last_output()
        self.assertTrue(len(output), len(hosts))
        client.join(output)
        for host in hosts:
            self.assertTrue(host in output)
            exit_code = output[host].exit_code
            self.assertTrue(exit_code == 0)

    def test_pssh_client_no_stdout_non_zero_exit_code_immediate_exit(self):
        output = self.client.run_command('exit 1')
        expected_exit_code = 1
        self.client.join(output)
        exit_code = output[self.host]['exit_code']
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))

    def test_pssh_client_run_command_get_output(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
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
        out = self.client.run_command(self.cmd)
        cmds = [cmd for host in out for cmd in [out[host]['cmd']]]
        output = {}
        for cmd in cmds:
            self.client.get_output(cmd, output)
        expected_exit_code = 0
        expected_stdout = [self.resp]
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

    def test_pssh_client_run_long_command(self):
        expected_lines = 5
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.client.join(output)
        self.assertTrue(self.host in output, msg="Got no output for command")
        stdout = list(output[self.host]['stdout'])
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))

    def test_pssh_client_auth_failure(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   user='FAKE USER',
                                   pkey=self.user_key)
        self.assertRaises(
            AuthenticationException, client.run_command, self.cmd)

    def test_pssh_client_hosts_list_part_failure(self):
        """Test getting output for remainder of host list in the case where one
        host in the host list has a failure"""
        hosts = [self.host, '127.1.1.100']
        client = ParallelSSHClient(hosts,
                                   port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False)
        self.assertFalse(client.finished(output))
        client.join(output, consume_output=True)
        self.assertTrue(client.finished(output))
        self.assertTrue(hosts[0] in output,
                        msg="Successful host does not exist in output - output is %s" % (output,))
        self.assertTrue(hosts[1] in output,
                        msg="Failed host does not exist in output - output is %s" % (output,))
        self.assertTrue('exception' in output[hosts[1]],
                        msg="Failed host %s has no exception in output - %s" % (hosts[1], output,))
        self.assertTrue(output[hosts[1]].exception is not None)
        try:
            raise output[hosts[1]]['exception']
        except ConnectionErrorException:
            pass
        else:
            raise Exception("Expected ConnectionError, got %s instead" % (
                output[hosts[1]]['exception'],))

    def test_pssh_client_timeout(self):
        # 1ms timeout
        client_timeout = 0.001
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key,
                                   timeout=client_timeout,
                                   num_retries=1)
        output = client.run_command('sleep 1', stop_on_errors=False)
        self.assertTrue(isinstance(output[self.host].exception,
                                   SessionError))

#     def test_pssh_client_run_command_password(self):
#         """Test password authentication. Embedded server accepts any password
#         even empty string"""
#         client = ParallelSSHClient([self.host], port=self.listen_port,
#                                    password='')
#         output = client.run_command(self.fake_cmd)
#         stdout = list(output[self.host]['stdout'])
#         self.assertTrue(self.host in output,
#                         msg="No output for host")
#         self.assertTrue(output[self.host]['exit_code'] == 0,
#                         msg="Expected exit code 0, got %s" % (
#                             output[self.host]['exit_code'],))
#         self.assertEqual(stdout, [self.fake_resp])

    def test_pssh_client_long_running_command_exit_codes(self):
        expected_lines = 2
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.client.join(output)
        self.assertTrue(self.host in output, msg="Got no output for command")
        self.assertTrue(not output[self.host]['exit_code'],
                        msg="Got exit code %s for still running cmd.." % (
                            output[self.host]['exit_code'],))
        self.assertFalse(self.client.finished(output))
        self.client.join(output, consume_output=True)
        self.assertTrue(self.client.finished(output))
        self.assertTrue(output[self.host]['exit_code'] == 0,
                        msg="Got non-zero exit code %s" % (
                            output[self.host]['exit_code'],))

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
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filepath = 'remote_test_dir', 'test_file_copy'
        remote_filename = os.path.sep.join([remote_test_dir, remote_filepath])
        remote_file_abspath = os.path.expanduser('~/' + remote_filename)
        remote_test_dir_abspath = os.path.expanduser('~/' + remote_test_dir)
        test_file = open(local_filename, 'w')
        test_file.writelines([test_file_data + os.linesep])
        test_file.close()
        cmds = client.copy_file(local_filename, remote_filename)
        cmds[0].get()
        try:
            self.assertTrue(os.path.isdir(remote_test_dir_abspath))
            self.assertTrue(os.path.isfile(remote_file_abspath))
            remote_file_data = open(remote_file_abspath, 'r').readlines()
            self.assertEqual(remote_file_data[0].strip(), test_file_data)
        except Exception:
            raise
        finally:
            os.unlink(remote_file_abspath)
            shutil.rmtree(remote_test_dir_abspath)
        # No directory
        remote_file_abspath = os.path.expanduser('~/' + remote_filepath)
        cmds = client.copy_file(local_filename, remote_filepath)
        try:
            gevent.joinall(cmds, raise_error=True)
        except Exception:
            raise
        finally:
            for filepath in [local_filename, remote_file_abspath]:
                os.unlink(filepath)
            try:
                os.unlink(remote_file_abspath)
            except OSError:
                pass

    def test_pssh_client_directory_relative_path(self):
        """Tests copying multiple directories with SSH client. Copy all the files from
        local directory to server, then make sure they are all present."""
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
        dir_name = os.path.dirname(__file__)
        remote_test_path_rel = os.sep.join(
            (dir_name.replace(os.path.expanduser('~') + os.sep, ''),
             remote_test_path))
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        for path in [local_test_path, remote_test_path_abs]:
            try:
                shutil.rmtree(path)
            except OSError:
                pass
        os.mkdir(local_test_path)
        remote_file_paths = []
        for i in range(0, 10):
            local_file_path_dir = os.path.join(
                local_test_path, 'sub_dir1', 'sub_dir2', 'dir_foo' + str(i))
            os.makedirs(local_file_path_dir)
            local_file_path = os.path.join(local_file_path_dir, 'foo' + str(i))
            remote_file_path = os.path.join(
                remote_test_path, 'sub_dir1', 'sub_dir2', 'dir_foo' + str(i), 'foo' + str(i))
            remote_file_paths.append(
                os.sep.join((os.path.dirname(__file__), remote_file_path)))
            test_file = open(local_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        cmds = client.copy_file(local_test_path, remote_test_path_rel, recurse=True)
        try:
            gevent.joinall(cmds, raise_error=True)
            for path in remote_file_paths:
                self.assertTrue(os.path.isfile(path))
        finally:
            shutil.rmtree(local_test_path)
            shutil.rmtree(remote_test_path_abs)

    def test_pssh_client_directory_abs_path(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
        dir_name = os.path.dirname(__file__)
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        for path in [local_test_path, remote_test_path_abs]:
            try:
                shutil.rmtree(path)
            except OSError:
                pass
        os.mkdir(local_test_path)
        remote_file_paths = []
        for i in range(0, 10):
            local_file_path_dir = os.path.join(
                local_test_path, 'sub_dir1', 'sub_dir2', 'dir_foo' + str(i))
            os.makedirs(local_file_path_dir)
            local_file_path = os.path.join(local_file_path_dir, 'foo' + str(i))
            remote_file_path = os.path.join(
                remote_test_path, 'sub_dir1', 'sub_dir2', 'dir_foo' + str(i), 'foo' + str(i))
            remote_file_paths.append(
                os.sep.join((os.path.dirname(__file__), remote_file_path)))
            test_file = open(local_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        cmds = client.copy_file(local_test_path, remote_test_path_abs, recurse=True)
        try:
            gevent.joinall(cmds, raise_error=True)
            for path in remote_file_paths:
                self.assertTrue(os.path.isfile(path))
        finally:
            shutil.rmtree(local_test_path)
            shutil.rmtree(remote_test_path_abs)

    def test_pssh_client_copy_file_failure(self):
        """Test failure scenarios of file copy"""
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
        dir_name = os.path.dirname(__file__)
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        for path in [local_test_path, remote_test_path_abs]:
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
        os.mkdir(remote_test_path_abs)
        local_file_path = os.path.join(local_test_path, 'test_file')
        remote_file_path = os.path.join(remote_test_path, 'test_file')
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        test_file = open(local_file_path, 'w')
        test_file.write('testing\n')
        test_file.close()
        # Permission errors on writing into dir
        mask = int('0111') if sys.version_info <= (2,) else 0o111
        os.chmod(remote_test_path_abs, mask)
        cmds = self.client.copy_file(local_test_path, remote_test_path_abs, recurse=True)
        try:
            gevent.joinall(cmds, raise_error=True)
            raise Exception("Expected SFTPError exception")
        except SFTPError:
            pass
        self.assertFalse(os.path.isfile(remote_test_path_abs))
        # Create directory tree failure test
        local_file_path = os.path.join(local_test_path, 'test_file')
        remote_file_path = os.path.join(remote_test_path, 'test_dir', 'test_file')
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        cmds = self.client.copy_file(local_file_path, remote_test_path_abs, recurse=True)
        try:
            gevent.joinall(cmds, raise_error=True)
            raise Exception("Expected SFTPError exception on creating remote "
                            "directory")
        except SFTPError:
            pass
        self.assertFalse(os.path.isfile(remote_test_path_abs))
        mask = int('0600') if sys.version_info <= (2,) else 0o600
        os.chmod(remote_test_path_abs, mask)
        for path in [local_test_path, remote_test_path_abs]:
            shutil.rmtree(path)

    def test_pssh_copy_remote_file_failure(self):
        cmds = self.client.copy_remote_file(
            'fakey fakey fake fake', 'equally fake')
        self.assertRaises(SFTPIOError, cmds[0].get)

    def test_pssh_copy_remote_file(self):
        """Test parallel copy file to local host"""
        test_file_data = 'test'
        dir_name = os.path.dirname(__file__)
        local_test_path = os.sep.join((dir_name, 'directory_test_local_remote_copied'))
        remote_test_path = 'directory_test_remote_copy'
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        remote_test_path_rel = os.sep.join(
            (dir_name.replace(os.path.expanduser('~') + os.sep, ''),
             remote_test_path))
        local_copied_dir = '_'.join([local_test_path, self.host])
        new_local_copied_dir = '.'.join([local_test_path, self.host])
        for path in [local_test_path, remote_test_path_abs, local_copied_dir,
                     new_local_copied_dir]:
            try:
                shutil.rmtree(path)
            except OSError:
                try:
                    os.unlink(path)
                except Exception:
                    pass
                pass
        os.mkdir(remote_test_path_abs)
        local_file_paths = []
        for i in range(0, 10):
            remote_file_path_dir = os.path.join(
                remote_test_path_abs, 'sub_dir', 'dir_foo' + str(i))
            os.makedirs(remote_file_path_dir)
            remote_file_path = os.path.join(remote_file_path_dir, 'foo' + str(i))
            local_file_path = os.path.join(
                local_copied_dir, 'sub_dir', 'dir_foo' + str(i), 'foo' + str(i))
            local_file_paths.append(local_file_path)
            test_file = open(remote_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        cmds = self.client.copy_remote_file(remote_test_path_abs, local_test_path)
        self.assertRaises(ValueError, gevent.joinall, cmds, raise_error=True)
        cmds = self.client.copy_remote_file(remote_test_path_abs, local_test_path,
                                            recurse=True)
        gevent.joinall(cmds, raise_error=True)
        try:
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        except Exception:
            shutil.rmtree(remote_test_path_abs)
        finally:
            shutil.rmtree(local_copied_dir)

        # Relative path
        cmds = self.client.copy_remote_file(remote_test_path_rel, local_test_path,
                                            recurse=True)
        gevent.joinall(cmds, raise_error=True)
        try:
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        except Exception:
            shutil.rmtree(remote_test_path_abs)
        finally:
            shutil.rmtree(local_copied_dir)

        # Different suffix
        cmds = self.client.copy_remote_file(remote_test_path_abs, local_test_path,
                                            suffix_separator='.', recurse=True)
        gevent.joinall(cmds, raise_error=True)
        new_local_copied_dir = '.'.join([local_test_path, self.host])
        try:
            for path in local_file_paths:
                path = path.replace(local_copied_dir, new_local_copied_dir)
                self.assertTrue(os.path.isfile(path))
        finally:
            shutil.rmtree(new_local_copied_dir)
            shutil.rmtree(remote_test_path_abs)

    def test_pssh_pool_size(self):
        """Test setting pool size to non default values"""
        hosts = ['host-%01d' % d for d in range(5)]
        pool_size = 2
        client = ParallelSSHClient(hosts, pool_size=pool_size)
        expected, actual = pool_size, client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))
        hosts = ['host-%01d' % d for d in range(15)]
        pool_size = 5
        client = ParallelSSHClient(hosts, pool_size=pool_size)
        expected, actual = client.pool_size, client.pool.size
        self.assertEqual(expected, actual,
                         msg="Expected pool size to be %s, got %s" % (
                             expected, actual,))
        hosts = ['host-%01d' % d for d in range(15)]
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
        server2 = OpenSSHServer(listen_ip=host2)
        server2.start_server()
        hosts = [self.host, host2]
        client = ParallelSSHClient(hosts,
                                   port=self.port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.cmd)
        stdout = [list(output[k].stdout) for k in output]
        expected_stdout = [[self.resp] for _ in hosts]
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        self.assertEqual(expected_stdout, stdout,
                         msg="Did not get expected output from all hosts. \
                         Got %s - expected %s" % (stdout, expected_stdout,))
        del client
        server2.stop()

    def test_pssh_hosts_iterator_hosts_modification(self):
        """Test using iterator as host list and modifying host list in place"""
        host2, host3 = '127.0.0.2', '127.0.0.3'
        server2 = OpenSSHServer(listen_ip=host2) 
        server3 = OpenSSHServer(listen_ip=host3)
        server2.start_server()
        server3.start_server()
        hosts = [self.host, '127.0.0.2']
        client = ParallelSSHClient(iter(hosts),
                                   port=self.port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.cmd)
        stdout = [list(output[k]['stdout']) for k in output]
        expected_stdout = [[self.resp], [self.resp]]
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        # Run again without re-assigning host list, should do nothing
        output = client.run_command(self.cmd)
        self.assertFalse(hosts[0] in output,
                         msg="Expected no host output, got %s" % (output,))
        self.assertFalse(output,
                         msg="Expected empty output, got %s" % (output,))
        # Re-assigning host list with new hosts should work
        hosts = ['127.0.0.2', '127.0.0.3']
        client.hosts = iter(hosts)
        output = client.run_command(self.cmd)
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        self.assertTrue(hosts[1] in output,
                        msg="Did not get output for new host %s" % (hosts[1],))
        server2.stop()
        server3.stop()

#     def test_ssh_proxy(self):
#         """Test connecting to remote destination via SSH proxy
#         client -> proxy -> destination
#         Proxy SSH server accepts no commands and sends no responses, only
#         proxies to destination. Destination accepts a command as usual."""
#         del self.client
#         self.client = None
#         self.server.kill()
#         server, _ = start_server_from_ip(self.host, port=self.listen_port)
#         proxy_host = '127.0.0.2'
#         proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
#         client = ParallelSSHClient([self.host], port=self.listen_port,
#                                    pkey=self.user_key,
#                                    proxy_host=proxy_host,
#                                    proxy_port=proxy_server_port,
#                                    )
#         try:
#             output = client.run_command(self.fake_cmd)
#             stdout = list(output[self.host]['stdout'])
#             expected_stdout = [self.fake_resp]
#             self.assertEqual(expected_stdout, stdout,
#                              msg="Got unexpected stdout - %s, expected %s" % 
#                              (stdout,
#                               expected_stdout,))
#         finally:
#             del client
#             server.kill()
#             proxy_server.kill()

#     def test_ssh_proxy_target_host_failure(self):
#         del self.client
#         self.client = None
#         self.server.kill()
#         proxy_host = '127.0.0.2'
#         proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
#         client = ParallelSSHClient([self.host], port=self.listen_port,
#                                    pkey=self.user_key,
#                                    proxy_host=proxy_host,
#                                    proxy_port=proxy_server_port,
#                                    )
#         try:
#             self.assertRaises(
#                 ConnectionErrorException, client.run_command, self.fake_cmd)
#         finally:
#             del client
#             proxy_server.kill()

#     def test_ssh_proxy_auth(self):
#         """Test connecting to remote destination via SSH proxy
#         client -> proxy -> destination
#         Proxy SSH server accepts no commands and sends no responses, only
#         proxies to destination. Destination accepts a command as usual."""
#         host2 = '127.0.0.2'
#         proxy_server, proxy_server_port = start_server_from_ip(host2)
#         proxy_user = 'proxy_user'
#         proxy_password = 'fake'
#         client = ParallelSSHClient([self.host], port=self.listen_port,
#                                    pkey=self.user_key,
#                                    proxy_host=host2,
#                                    proxy_port=proxy_server_port,
#                                    proxy_user=proxy_user,
#                                    proxy_password='fake',
#                                    proxy_pkey=self.user_key,
#                                    num_retries=1,
#                                    )
#         expected_stdout = [self.fake_resp]
#         try:
#             output = client.run_command(self.fake_cmd)
#             stdout = list(output[self.host]['stdout'])
#             self.assertEqual(expected_stdout, stdout,
#                             msg="Got unexpected stdout - %s, expected %s" % (
#                                 stdout, expected_stdout,))
#             self.assertEqual(client.host_clients[self.host].proxy_user,
#                              proxy_user)
#             self.assertEqual(client.host_clients[self.host].proxy_password,
#                              proxy_password)
#             self.assertTrue(client.host_clients[self.host].proxy_pkey)
#         finally:
#             del client
#             proxy_server.kill()

#     def test_ssh_proxy_auth_fail(self):
#         """Test failures while connecting via proxy"""
#         proxy_host = '127.0.0.2'
#         server, listen_port = start_server_from_ip(self.host, fail_auth=True)
#         proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
#         proxy_user = 'proxy_user'
#         proxy_password = 'fake'
#         client = ParallelSSHClient([self.host], port=listen_port,
#                                    pkey=self.user_key,
#                                    proxy_host='127.0.0.2',
#                                    proxy_port=proxy_server_port,
#                                    proxy_user=proxy_user,
#                                    proxy_password='fake',
#                                    proxy_pkey=self.user_key,
#                                    num_retries=1,
#                                    )
#         try:
#             self.assertRaises(
#                 AuthenticationException, client.run_command, self.fake_cmd)
#         finally:
#             del client
#             server.kill()
#             proxy_server.kill()

    def test_bash_variable_substitution(self):
        """Test bash variables work correctly"""
        command = """for i in 1 2 3; do echo $i; done"""
        output = list(self.client.run_command(command)[self.host]['stdout'])
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
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
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
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
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
        # server, port = start_server_from_ip(self.host, fail_auth=True)
        hosts = [self.host]
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey='A REALLY FAKE KEY',
                                   num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False)
        self.assertTrue('exception' in output[self.host],
                        msg="Got no exception for host %s - expected connection error" % (
                            self.host,))
        try:
            raise output[self.host]['exception']
        except AuthenticationException as ex:
            self.assertEqual(ex.args[1], self.host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.args[1], self.host,))
            self.assertEqual(ex.args[2], self.port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], self.port,))
        else:
            raise Exception("Expected AuthenticationException")

    def test_multiple_single_quotes_in_cmd(self):
        """Test that we can run a command with multiple single quotes"""
        output = self.client.run_command("echo 'me' 'and me'")
        stdout = list(output[self.host].stdout)
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
        hosts = [('127.0.0.%01d' % n, self.make_random_port())
                 for n in range(1,3)]
        host_config = dict.fromkeys([h for h,_ in hosts])
        servers = []
        password = 'overriden_pass'
        fake_key = 'FAKE KEY'
        for host, port in hosts:
            server = OpenSSHServer(listen_ip=host, port=port)
            server.start_server()
            host_config[host] = {}
            host_config[host]['port'] = port
            host_config[host]['user'] = self.user
            host_config[host]['password'] = password
            host_config[host]['private_key'] = self.user_key
            servers.append(server)
        host_config[hosts[1][0]]['private_key'] = fake_key
        client = ParallelSSHClient([h for h, _ in hosts], host_config=host_config)
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
        for host, _ in hosts:
            self.assertTrue(host in output)
        try:
            raise output[hosts[1][0]]['exception']
        except AuthenticationException as ex:
            pass
        else:
            raise AssertionError("Expected AutnenticationException on host %s",
                                 hosts[0][0])
        self.assertTrue(output[hosts[1][0]].exit_code is None,
                        msg="Execution failed on host %s" % (hosts[1][0],))
        self.assertTrue(client.host_clients[hosts[0][0]].user == self.user,
                        msg="Host config user override failed")
        self.assertTrue(client.host_clients[hosts[0][0]].password == password,
                        msg="Host config password override failed")
        self.assertTrue(client.host_clients[hosts[0][0]].pkey == self.user_key,
                        msg="Host config pkey override failed")
        for server in servers:
            server.stop()

    def test_pssh_client_override_allow_agent_authentication(self):
        """Test running command with allow_agent set to False"""
        client = ParallelSSHClient([self.host],
                                   port=self.port,
                                   allow_agent=False,
                                   pkey=self.user_key)
        output = client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
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

    def test_get_exit_codes_bad_output(self):
        self.assertFalse(self.client.get_exit_codes({}))
        self.assertFalse(self.client.get_exit_code({}))

    def test_per_host_tuple_args(self):
        host2, host3 = '127.0.0.4', '127.0.0.5'
        server2 = OpenSSHServer(host2)
        server3 = OpenSSHServer(host3)
        servers = [server2, server3]
        for server in servers:
            server.start_server()
        time.sleep(1)
        hosts = [self.host, host2, host3]
        host_args = ('arg1', 'arg2', 'arg3')
        cmd = 'echo %s'
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=2)
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
        # Invalid number of args
        host_args = (('arg1', ),)
        self.assertRaises(
            TypeError, client.run_command, cmd, host_args=host_args)
        for server in servers:
            server.stop()

    def test_per_host_dict_args(self):
        host2, host3 = '127.0.0.2', '127.0.0.3'
        server2 = OpenSSHServer(host2)
        server3 = OpenSSHServer(host3)
        servers = [server2, server3]
        for server in servers:
            server.start_server()
        hosts = [self.host, host2, host3]
        hosts_gen = (h for h in hosts)
        host_args = [dict(zip(('host_arg1', 'host_arg2',),
                              ('arg1-%s' % (i,), 'arg2-%s' % (i,),)))
                     for i, _ in enumerate(hosts)]
        cmd = 'echo %(host_arg1)s %(host_arg2)s'
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1)
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
        _utf16 = u'é'.encode('utf-8').decode('utf-16')
        cmd = u"echo 'é'"
        output = self.client.run_command(cmd)
        stdout = list(output[self.host].stdout)
        self.assertEqual(expected, stdout,
                         msg="Got unexpected unicode output %s - expected %s" % (
                             stdout, expected,))
        output = self.client.run_command(cmd, encoding='utf-16')
        _stdout = list(output[self.host].stdout)
        self.assertEqual([_utf16], _stdout)

    def test_pty(self):
        cmd = "echo 'asdf' >&2"
        expected_stderr = ['asdf']
        output = self.client.run_command(cmd)
        self.client.join(output)
        stdout = list(output[self.host].stdout)
        stderr = list(output[self.host].stderr)
        exit_code = output[self.host].exit_code
        self.assertEqual([], stdout)
        self.assertEqual(expected_stderr, stderr)
        self.assertTrue(exit_code == 0)
        output = self.client.run_command(cmd, use_pty=True)
        stdout = list(output[self.host].stdout)
        stderr = list(output[self.host].stderr)
        exit_code = output[self.host].exit_code
        expected_stdout = []
        # With a PTY, stdout and stderr are combined into stdout
        self.assertEqual(expected_stderr, stdout)
        self.assertEqual([], stderr)
        self.assertTrue(exit_code == 0)

    def test_output_attributes(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
        expected_stderr = []
        self.client.join(output)
        exit_code = output[self.host]['exit_code']
        stdout = list(output[self.host]['stdout'])
        stderr = list(output[self.host]['stderr'])
        host_output = output[self.host]
        self.assertEqual(expected_exit_code, host_output.exit_code)
        self.assertEqual(expected_exit_code, host_output['exit_code'])
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

    def test_run_command_user_sudo(self):
        user = 'fakey_fake_user'
        output = self.client.run_command(self.cmd, user=user)
        self.client.join(output)
        stderr = list(output[self.host].stderr)
        self.assertTrue(len(stderr) > 0)
        self.assertTrue(output[self.host].exit_code == 1)

    def test_run_command_shell(self):
        output = self.client.run_command(self.cmd, shell="bash -c")
        self.client.join(output)
        stdout = list(output[self.host].stdout)
        self.assertEqual(stdout, [self.resp])

    def test_run_command_shell_sudo(self):
        output = self.client.run_command(self.cmd,
                                         shell="bash -c",
                                         sudo=True)
        self.assertTrue(self.host in output)
        self.assertTrue(output[self.host].channel is not None)

    def test_run_command_sudo(self):
        output = self.client.run_command(self.cmd, sudo=True)
        self.assertTrue(self.host in output)
        self.assertTrue(output[self.host].channel is not None)

    def test_conn_failure(self):
        """Test connection error failure case - ConnectionErrorException"""
        client = ParallelSSHClient(['127.0.0.100'], port=self.port,
                                   num_retries=0)
        self.assertRaises(ConnectionErrorException,
                          client.run_command, self.cmd)

    def test_retries(self):
        client = ParallelSSHClient(['127.0.0.100'], port=self.port,
                                   num_retries=2, retry_delay=1)
        self.assertRaises(ConnectionErrorException, client.run_command, self.cmd)
        host = ''.join([random.choice(string.ascii_letters) for n in range(8)])
        client.hosts = [host]
        self.assertRaises(UnknownHostException, client.run_command, self.cmd)

    def test_unknown_host_failure(self):
        """Test connection error failure case - ConnectionErrorException"""
        host = ''.join([random.choice(string.ascii_letters) for n in range(8)])
        client = ParallelSSHClient([host], port=self.port,
                                   num_retries=1)
        self.assertRaises(UnknownHostException, client.run_command, self.cmd)

    def test_open_channel_failure(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        client.join(client.run_command(self.cmd))
        client.host_clients[self.host].session.disconnect()
        self.assertRaises(SessionError, client.host_clients[self.host].open_session)

    def test_host_no_client(self):
        output = {'blah': None}
        self.client.join(output)

#     def test_proxy_remote_host_failure_timeout(self):
#         """Test that timeout setting is passed on to proxy to be used for the
#         proxy->remote host connection timeout
#         """
#         self.server.kill()
#         server_timeout=0.2
#         client_timeout=server_timeout-0.1
#         server, listen_port = start_server_from_ip(self.host,
#                                                    timeout=server_timeout)
#         proxy_host = '127.0.0.2'
#         proxy_server, proxy_server_port = start_server_from_ip(proxy_host)
#         proxy_user = 'proxy_user'
#         proxy_password = 'fake'
#         client = ParallelSSHClient([self.host], port=listen_port,
#                                    pkey=self.user_key,
#                                    proxy_host='127.0.0.2',
#                                    proxy_port=proxy_server_port,
#                                    proxy_user=proxy_user,
#                                    proxy_password='fake',
#                                    proxy_pkey=self.user_key,
#                                    num_retries=1,
#                                    timeout=client_timeout,
#                                    )
#         try:
#             self.assertRaises(
#                 ConnectionErrorException, client.run_command, self.fake_cmd)
#         finally:
#             del client
#             server.kill()
#             proxy_server.kill()
