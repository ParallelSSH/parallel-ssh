# -*- coding: utf-8 -*-
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


"""Unittests for :mod:`pssh.ParallelSSHClient` class"""

import unittest
import pwd
import os
import shutil
import sys
import string
import random
from datetime import datetime
from platform import python_version

from pytest import mark
from gevent import joinall, spawn, socket, Greenlet, sleep
from pssh.config import HostConfig
from pssh.clients.native import ParallelSSHClient
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError, PKeyFileError
from pssh.output import HostOutput

from .base_ssh2_case import PKEY_FILENAME, PUB_FILE
from ..embedded_server.openssh import OpenSSHServer


class ParallelSSHClientTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.host = '127.0.0.1'
        cls.port = 2223
        cls.server = OpenSSHServer(listen_ip=cls.host, port=cls.port)
        cls.server.start_server()
        cls.cmd = 'echo me'
        cls.resp = u'me'
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
        del cls.server

    def setUp(self):
        self.long_cmd = lambda lines: 'for (( i=0; i<%s; i+=1 )) do echo $i; sleep 1; done' % (lines,)

    def make_random_port(self, host=None):
        host = '127.0.0.1' if host is None else host
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        listen_port = sock.getsockname()[1]
        sock.close()
        return listen_port

    def test_client_join_consume_output(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        self.client.join(output, consume_output=True)
        exit_code = output[0].exit_code
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        self.assertEqual(len(stdout), 0)
        self.assertEqual(len(stderr), 0)
        self.assertEqual(expected_exit_code, exit_code)
        output = self.client.run_command('echo "me" >&2', use_pty=False)
        self.client.join(output, consume_output=True)
        exit_code = output[0].exit_code
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        self.assertTrue(len(stdout) == 0)
        self.assertTrue(len(stderr) == 0)
        self.assertEqual(expected_exit_code, exit_code)

    def test_client_join_stdout(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
        expected_stderr = []
        self.client.join(output)
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        exit_code = output[0].exit_code
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
        self.client.join(output, consume_output=True)
        exit_code = output[0].exit_code
        self.assertTrue(exit_code == 1)
        self.assertTrue(len(output), len(self.client.cmds))
        _output = [cmd.get() for cmd in self.client.cmds]
        self.assertTrue(len(_output) == len(output))

    def test_pssh_client_no_stdout_non_zero_exit_code_immediate_exit(self):
        output = self.client.run_command('exit 1', return_list=True)
        expected_exit_code = 1
        self.client.join(output)
        exit_code = output[0].exit_code
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))

    def test_pssh_client_no_stdout_non_zero_exit_code_immediate_exit_no_join(self):
        output = self.client.run_command('exit 1', return_list=True)
        expected_exit_code = 1
        for host_out in output:
            for line in host_out.stdout:
                pass
        exit_code = output[0].exit_code
        self.assertEqual(expected_exit_code, exit_code)

    def test_pssh_client_run_command_get_output(self):
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
        expected_stderr = []
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        exit_code = output[0].exit_code
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
        stdout = list(output[0].stdout)
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
        self.assertEqual(len(hosts), len(output))
        self.assertIsNotNone(output[1].exception)
        self.assertEqual(output[1].exception.host, hosts[1])
        try:
            raise output[1].exception
        except ConnectionErrorException:
            pass
        else:
            raise Exception("Expected ConnectionError, got %s instead" % (
                output[1].exception,))

    def test_pssh_client_timeout(self):
        # 1ms timeout
        client_timeout = 0.001
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key,
                                   timeout=client_timeout,
                                   num_retries=1)
        output = client.run_command('sleep 1', stop_on_errors=False)
        self.assertIsInstance(output[0].exception,
                              Timeout)

    def test_connection_timeout(self):
        client_timeout = .01
        host = 'fakehost.com'
        client = ParallelSSHClient([host], port=self.port,
                                   pkey=self.user_key,
                                   timeout=client_timeout,
                                   num_retries=1)
        output = client.run_command('sleep 1', stop_on_errors=False)
        self.assertIsInstance(output[0].exception, ConnectionErrorException)

    def test_zero_timeout(self):
        host = '127.0.0.2'
        server = OpenSSHServer(listen_ip=host, port=self.port)
        server.start_server()
        client = ParallelSSHClient([self.host, host],
                                   port=self.port,
                                   pkey=self.user_key,
                                   timeout=0)
        cmd = spawn(client.run_command, 'sleep 1', stop_on_errors=False)
        output = cmd.get(timeout=3)
        self.assertTrue(output[0].exception is None)

    def test_pssh_client_long_running_command_exit_codes(self):
        expected_lines = 2
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.client.join(output)
        self.assertIsNone(output[0].exit_code,
                        msg="Got exit code %s for still running cmd.." % (
                            output[0].exit_code,))
        self.assertFalse(self.client.finished(output))
        self.client.join(output, consume_output=True)
        self.assertTrue(self.client.finished(output))
        self.assertEqual(output[0].exit_code, 0)

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
        port = self.make_random_port(host=self.host)
        client = ParallelSSHClient([self.host], port=port, num_retries=1)
        cmds = client.copy_file("test", "test")
        client.pool.join()
        for cmd in cmds:
            try:
                cmd.get()
            except Exception as ex:
                self.assertEqual(ex.host, self.host)
                self.assertIsInstance(ex, ConnectionErrorException)
            else:
                raise Exception("Expected ConnectionErrorException, got none")

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
            try:
                os.unlink(remote_file_abspath)
            except OSError:
                pass
            try:
                shutil.rmtree(remote_test_dir_abspath)
            except Exception:
                pass
        # No directory
        remote_file_abspath = os.path.expanduser('~/' + remote_filepath)
        cmds = client.copy_file(local_filename, remote_filepath)
        try:
            joinall(cmds, raise_error=True)
        except Exception:
            raise
        finally:
            for filepath in [local_filename, remote_file_abspath]:
                os.unlink(filepath)
            try:
                os.unlink(remote_file_abspath)
            except OSError:
                pass

    def test_pssh_copy_file_per_host_args(self):
        """Test parallel copy file with per-host arguments"""
        host2, host3 = '127.0.0.6', '127.0.0.7'
        server2 = OpenSSHServer(host2, port=self.port)
        server3 = OpenSSHServer(host3, port=self.port)
        servers = [server2, server3]
        for server in servers:
            server.start_server()
        hosts = [self.host, host2, host3]

        local_file_prefix = 'test_file_'
        remote_file_prefix = 'test_remote_'

        copy_args = [dict(zip(('local_file', 'remote_file',),
                              (local_file_prefix + str(i + 1),
                               remote_file_prefix + str(i + 1),)
                              ))
                     for i, _ in enumerate(hosts)]

        test_file_data = 'test'
        for i, _ in enumerate(hosts):
            test_file = open(local_file_prefix + str(i + 1), 'w')
            test_file.writelines([test_file_data + os.linesep])
            test_file.close()

        client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                   num_retries=2)
        greenlets = client.copy_file('%(local_file)s', '%(remote_file)s',
                                     copy_args=copy_args)
        joinall(greenlets)

        self.assertRaises(HostArgumentException, client.copy_file,
                          '%(local_file)s', '%(remote_file)s',
                          copy_args=[copy_args[0]])
        try:
            for i, _ in enumerate(hosts):
                remote_file_abspath = os.path.expanduser(
                    '~/' + remote_file_prefix + str(i + 1))
                self.assertTrue(os.path.isfile(remote_file_abspath))
                remote_file_data = open(
                    remote_file_abspath, 'r').readlines()
                self.assertEqual(
                    remote_file_data[0].strip(), test_file_data)
        except Exception:
            raise
        finally:
            for i, _ in enumerate(hosts):
                remote_file_abspath = os.path.expanduser(
                        '~/' + remote_file_prefix + str(i + 1))
                local_file_path = local_file_prefix + str(i + 1)
                os.unlink(remote_file_abspath)
                os.unlink(local_file_path)

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
            joinall(cmds, raise_error=True)
            for path in remote_file_paths:
                self.assertTrue(os.path.isfile(path))
        finally:
            for _path in (local_test_path, remote_test_path_abs):
                try:
                    shutil.rmtree(_path)
                except Exception:
                    pass

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
            joinall(cmds, raise_error=True)
            for path in remote_file_paths:
                self.assertTrue(os.path.isfile(path))
        finally:
            for _path in (local_test_path, remote_test_path_abs):
                try:
                    shutil.rmtree(_path)
                except Exception:
                    pass

    def test_pssh_client_copy_file_failure(self):
        """Test failure scenarios of file copy"""
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
        dir_name = os.path.dirname(__file__)
        remote_test_path_abs = os.sep.join((dir_name, remote_test_path))
        for path in [local_test_path, remote_test_path_abs]:
            mask = 0o700
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
        mask = 0o111
        os.chmod(remote_test_path_abs, mask)
        cmds = self.client.copy_file(local_test_path, remote_test_path_abs, recurse=True)
        try:
            joinall(cmds, raise_error=True)
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
            joinall(cmds, raise_error=True)
            raise Exception("Expected SFTPError exception on creating remote "
                            "directory")
        except SFTPError:
            pass
        self.assertFalse(os.path.isfile(remote_test_path_abs))
        mask = 0o600
        os.chmod(remote_test_path_abs, mask)
        for path in [local_test_path, remote_test_path_abs]:
            try:
                shutil.rmtree(path)
            except Exception:
                pass

    def test_pssh_copy_remote_file_failure(self):
        cmds = self.client.copy_remote_file(
            'fakey fakey fake fake', 'equally fake')
        try:
            cmds[0].get()
        except Exception as ex:
            self.assertEqual(ex.host, self.host)
            self.assertIsInstance(ex, SFTPIOError)
        else:
            raise Exception("Expected SFTPIOError, got none")

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
        self.assertRaises(ValueError, joinall, cmds, raise_error=True)
        cmds = self.client.copy_remote_file(remote_test_path_abs, local_test_path,
                                            recurse=True)
        joinall(cmds, raise_error=True)
        try:
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        except Exception:
            try:
                shutil.rmtree(remote_test_path_abs)
            except Exception:
                pass
            raise
        finally:
            try:
                shutil.rmtree(local_copied_dir)
            except Exception:
                pass

        # Relative path
        cmds = self.client.copy_remote_file(remote_test_path_rel, local_test_path,
                                            recurse=True)
        joinall(cmds, raise_error=True)
        try:
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        finally:
            try:
                shutil.rmtree(local_copied_dir)
            except Exception:
                pass

        # Different suffix
        cmds = self.client.copy_remote_file(remote_test_path_abs, local_test_path,
                                            suffix_separator='.', recurse=True)
        joinall(cmds, raise_error=True)
        new_local_copied_dir = '.'.join([local_test_path, self.host])
        try:
            for path in local_file_paths:
                path = path.replace(local_copied_dir, new_local_copied_dir)
                self.assertTrue(os.path.isfile(path))
        finally:
            for _path in (new_local_copied_dir, remote_test_path_abs):
                try:
                    shutil.rmtree(_path)
                except Exception:
                    pass

    def test_pssh_copy_remote_file_per_host_args(self):
        """Test parallel remote copy file with per-host arguments"""
        host2, host3 = '127.0.0.10', '127.0.0.11'
        server2 = OpenSSHServer(host2, port=self.port)
        server3 = OpenSSHServer(host3, port=self.port)
        servers = [server2, server3]
        for server in servers:
            server.start_server()
        hosts = [self.host, host2, host3]

        remote_file_prefix = 'test_file_'
        local_file_prefix = 'test_local_'

        copy_args = [dict(zip(('remote_file', 'local_file',),
                              (remote_file_prefix + str(i + 1),
                               local_file_prefix + str(i + 1),)
                              ))
                     for i, _ in enumerate(hosts)]

        test_file_data = 'test'
        for i, _ in enumerate(hosts):
            remote_file_abspath = os.path.expanduser(
                '~/' + remote_file_prefix + str(i + 1))
            test_file = open(remote_file_abspath, 'w')
            test_file.writelines([test_file_data + os.linesep])
            test_file.close()

        client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                   num_retries=2)
        greenlets = client.copy_remote_file('%(remote_file)s', '%(local_file)s',
                                            copy_args=copy_args)
        joinall(greenlets)

        self.assertRaises(HostArgumentException, client.copy_remote_file,
                          '%(remote_file)s', '%(local_file)s',
                          copy_args=[copy_args[0]])
        try:
            for i, _ in enumerate(hosts):
                local_file_path = local_file_prefix + str(i + 1)
                self.assertTrue(os.path.isfile(local_file_path))
                local_file_data = open(local_file_path, 'r').readlines()
                self.assertEqual(local_file_data[0].strip(), test_file_data)
        except Exception:
            raise
        finally:
            for i, _ in enumerate(hosts):
                remote_file_abspath = os.path.expanduser(
                        '~/' + remote_file_prefix + str(i + 1))
                local_file_path = local_file_prefix + str(i + 1)
                try:
                    os.unlink(remote_file_abspath)
                    os.unlink(local_file_path)
                except OSError:
                    pass

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
        server2 = OpenSSHServer(listen_ip=host2, port=self.port)
        server2.start_server()
        hosts = [self.host, host2]
        client = ParallelSSHClient(hosts,
                                   port=self.port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.cmd)
        stdout = [list(host_out.stdout) for host_out in output]
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
        server2 = OpenSSHServer(listen_ip=host2, port=self.port)
        server3 = OpenSSHServer(listen_ip=host3, port=self.port)
        for _server in (server2, server3):
            _server.start_server()
        hosts = [self.host, '127.0.0.2']
        client = ParallelSSHClient(iter(hosts),
                                   port=self.port,
                                   pkey=self.user_key,
                                   pool_size=1,
                                   )
        output = client.run_command(self.cmd)
        stdout = [host_out.stdout for host_out in output]
        expected_stdout = [[self.resp], [self.resp]]
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        # Run again without re-assigning host list, should do nothing
        output = client.run_command(self.cmd)
        self.assertEqual(len(output), 0)
        # Re-assigning host list with new hosts should work
        hosts = ['127.0.0.2', '127.0.0.3']
        client.hosts = iter(hosts)
        output = client.run_command(self.cmd)
        self.assertEqual(len(hosts), len(output),
                         msg="Did not get output from all hosts. Got output for " \
                         "%s/%s hosts" % (len(output), len(hosts),))
        self.assertEqual(output[1].host, hosts[1],
                         msg="Did not get output for new host %s" % (hosts[1],))
        server2.stop()
        server3.stop()

    def test_bash_variable_substitution(self):
        """Test bash variables work correctly"""
        command = """for i in 1 2 3; do echo $i; done"""
        host_output = self.client.run_command(command)[0]
        output = list(host_output.stdout)
        expected = ['1','2','3']
        self.assertListEqual(output, expected)

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
        self.assertEqual(len(hosts), len(output))

    def test_identical_hosts_in_host_list(self):
        """Test that we can handle identical hosts in host list"""
        host2 = '127.0.0.2'
        hosts = [self.host, host2, self.host, self.host]
        _server2 = OpenSSHServer(listen_ip=host2, port=self.port)
        _server2.start_server()
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False, return_list=True)
        client.join(output)
        self.assertEqual(len(hosts), len(output),
                         msg="Host list contains %s identical hosts, only got output for %s" % (
                             len(hosts), len(output)))
        for host_i, host in enumerate(hosts):
            single_client = client._host_clients[(host_i, host)]
            self.assertEqual(single_client.host, host)
        expected_stdout = [self.resp]
        for host_out in output:
            _host_stdout = list(host_out.stdout)
            self.assertListEqual(_host_stdout, expected_stdout)

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
        self.assertIsNotNone(output[0].exception)
        for host_output in output:
            exit_code = host_output.exit_code
            self.assertEqual(exit_code, None)
        try:
            raise output[0].exception
        except ConnectionErrorException as ex:
            self.assertEqual(ex.host, host,
                             msg="Exception host argument is %s, should be %s" % (
                                 ex.host, host,))
            self.assertEqual(ex.args[2], port,
                             msg="Exception port argument is %s, should be %s" % (
                                 ex.args[2], port,))
        else:
            raise Exception("Expected ConnectionErrorException")

    def test_bad_pkey_path(self):
        self.assertRaises(PKeyFileError, ParallelSSHClient, [self.host], port=self.port,
                          pkey='A REALLY FAKE KEY',
                          num_retries=1)

    def test_multiple_single_quotes_in_cmd(self):
        """Test that we can run a command with multiple single quotes"""
        output = self.client.run_command("echo 'me' 'and me'")
        stdout = list(output[0].stdout)
        expected = 'me and me'
        self.assertTrue(len(stdout)==1,
                        msg="Got incorrect number of lines in output - %s" % (stdout,))
        self.assertEqual(output[0].exit_code, 0)
        self.assertEqual(expected, stdout[0],
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout[0],))

    def test_backtics_in_cmd(self):
        """Test running command with backtics in it"""
        output = self.client.run_command("out=`ls` && echo $out")
        self.client.join(output, consume_output=True)
        self.assertEqual(output[0].exit_code, 0)

    def test_multiple_shell_commands(self):
        """Test running multiple shell commands in one go"""
        output = self.client.run_command("echo me; echo and; echo me")
        stdout = list(output[0].stdout)
        expected = ["me", "and", "me"]
        self.assertEqual(output[0].exit_code, 0)
        self.assertEqual(expected, stdout,
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout,))

    def test_escaped_quotes(self):
        """Test escaped quotes in shell variable are handled correctly"""
        output = self.client.run_command('t="--flags=\\"this\\""; echo $t')
        stdout = list(output[0].stdout)
        expected = ['--flags="this"']
        self.assertEqual(output[0].exit_code, 0)
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
        client = ParallelSSHClient([h for h, _ in hosts],
                                   host_config=host_config,
                                   num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
        self.assertEqual(len(hosts), len(output))
        try:
            raise output[1].exception
        except PKeyFileError as ex:
            self.assertEqual(ex.host, host)
        else:
            raise AssertionError("Expected ValueError on host %s",
                                 hosts[0][0])
        self.assertTrue(output[1].exit_code is None,
                        msg="Execution failed on host %s" % (hosts[1][0],))
        self.assertEqual(client._host_clients[0, hosts[0][0]].user, self.user)
        self.assertEqual(client._host_clients[0, hosts[0][0]].password, password)
        self.assertEqual(client._host_clients[0, hosts[0][0]].pkey, os.path.abspath(self.user_key))
        for server in servers:
            server.stop()

    def test_host_config_list_type(self):
        """Test per-host configuration functionality of ParallelSSHClient"""
        hosts = [('127.0.0.%01d' % n, self.make_random_port())
                 for n in range(1,3)]
        host_config = [HostConfig() for _ in hosts]
        servers = []
        password = 'overriden_pass'
        fake_key = 'FAKE KEY'
        for host_i, (host, port) in enumerate(hosts):
            server = OpenSSHServer(listen_ip=host, port=port)
            server.start_server()
            host_config[host_i].port = port
            host_config[host_i].user = self.user
            host_config[host_i].password = password
            host_config[host_i].private_key = self.user_key
            servers.append(server)
        host_config[1].private_key = fake_key
        client = ParallelSSHClient([h for h, _ in hosts],
                                   host_config=host_config,
                                   num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
        self.assertEqual(len(hosts), len(output))
        try:
            raise output[1].exception
        except PKeyFileError as ex:
            self.assertEqual(ex.host, host)
        else:
            raise AssertionError("Expected ValueError on host %s",
                                 hosts[0][0])
        self.assertTrue(output[1].exit_code is None,
                        msg="Execution failed on host %s" % (hosts[1][0],))
        self.assertEqual(client._host_clients[0, hosts[0][0]].user, self.user)
        self.assertEqual(client._host_clients[0, hosts[0][0]].password, password)
        self.assertEqual(client._host_clients[0, hosts[0][0]].pkey, os.path.abspath(self.user_key))
        for server in servers:
            server.stop()

    def test_host_config_bad_entries(self):
        hosts = ['localhost', 'localhost']
        host_config = [HostConfig()]
        self.assertRaises(ValueError, ParallelSSHClient, hosts, host_config=host_config)
        # Can't sanity check generators
        ParallelSSHClient(iter(hosts), host_config=host_config)

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
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        exit_code = output[0].exit_code
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

    def test_per_host_tuple_args(self):
        host2, host3 = '127.0.0.4', '127.0.0.5'
        server2 = OpenSSHServer(host2, port=self.port)
        server3 = OpenSSHServer(host3, port=self.port)
        servers = [server2, server3]
        for server in servers:
            server.start_server()
        hosts = [self.host, host2, host3]
        host_args = ('arg1', 'arg2', 'arg3')
        cmd = 'echo %s'
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=2)
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = [host_args[i]]
            stdout = list(output[i].stdout)
            self.assertEqual(expected, stdout)
            self.assertEqual(output[i].exit_code, 0)
        host_args = (('arg1', 'arg2'), ('arg3', 'arg4'), ('arg5', 'arg6'),)
        cmd = 'echo %s %s'
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%s %s" % host_args[i]]
            stdout = list(output[i].stdout)
            self.assertEqual(expected, stdout)
            self.assertEqual(output[i].exit_code, 0)
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
        server2 = OpenSSHServer(host2, port=self.port)
        server3 = OpenSSHServer(host3, port=self.port)
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
            stdout = list(output[i].stdout)
            self.assertEqual(expected, stdout)
            self.assertEqual(output[i].exit_code, 0)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])
        # Host list generator should work also
        client.hosts = hosts_gen
        output = client.run_command(cmd, host_args=host_args)
        for i, host in enumerate(hosts):
            expected = ["%(host_arg1)s %(host_arg2)s" % host_args[i]]
            stdout = list(output[i].stdout)
            self.assertEqual(expected, stdout)
            self.assertEqual(output[i].exit_code, 0)
        client.hosts = (h for h in hosts)
        self.assertRaises(HostArgumentException, client.run_command,
                          cmd, host_args=[host_args[0]])

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
        stdout = list(output[0].stdout)
        self.assertEqual(expected, stdout,
                         msg="Got unexpected unicode output %s - expected %s" % (
                             stdout, expected,))
        output = self.client.run_command(cmd, encoding='utf-16')
        _stdout = list(output[0].stdout)
        self.assertEqual([_utf16], _stdout)

    def test_ssh_client_utf_encoding_join(self):
        _utf16 = u'é'.encode('utf-8').decode('utf-16')
        cmd = u"echo 'é'"
        output = self.client.run_command(cmd, encoding='utf-16')
        self.client.join(output, encoding='utf-16')
        stdout = list(output[0].stdout)
        self.assertEqual([_utf16], stdout)

    def test_pty(self):
        cmd = "echo 'asdf' >&2"
        expected_stderr = ['asdf']
        output = self.client.run_command(cmd)
        self.client.join(output)
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        exit_code = output[0].exit_code
        self.assertEqual([], stdout)
        self.assertEqual(expected_stderr, stderr)
        self.assertTrue(exit_code == 0)
        output = self.client.run_command(cmd, use_pty=True)
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        exit_code = output[0].exit_code
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
        exit_code = output[0].exit_code
        stdout = list(output[0].stdout)
        stderr = list(output[0].stderr)
        host_output = output[0]
        self.assertTrue(hasattr(output[0], 'host'))
        self.assertTrue(hasattr(output[0], 'channel'))
        self.assertTrue(hasattr(output[0], 'stdout'))
        self.assertTrue(hasattr(output[0], 'stderr'))
        self.assertTrue(hasattr(output[0], 'stdin'))
        self.assertTrue(hasattr(output[0], 'exception'))
        self.assertTrue(hasattr(output[0], 'exit_code'))

    def test_run_command_user_sudo(self):
        user = 'fakey_fake_user'
        output = self.client.run_command(self.cmd, user=user)
        self.client.join(output)
        stderr = list(output[0].stderr)
        self.assertTrue(len(stderr) > 0)
        self.assertEqual(output[0].exit_code, 1)

    def test_run_command_shell(self):
        output = self.client.run_command(self.cmd, shell="bash -c")
        self.client.join(output)
        stdout = list(output[0].stdout)
        self.assertEqual(stdout, [self.resp])

    def test_run_command_shell_sudo(self):
        output = self.client.run_command(self.cmd,
                                         shell="bash -c",
                                         sudo=True)
        self.assertEqual(len(output), len(self.client.hosts))
        self.assertTrue(output[0].channel is not None)

    def test_run_command_sudo(self):
        output = self.client.run_command(self.cmd, sudo=True)
        self.assertEqual(len(output), len(self.client.hosts))
        self.assertTrue(output[0].channel is not None)

    @unittest.skipUnless(bool(os.getenv('TRAVIS')), "Not on Travis CI - skipping")
    def test_run_command_sudo_var(self):
        command = """for i in 1 2 3; do echo $i; done"""
        output = list(self.client.run_command(
            command, sudo=True)[0].stdout)
        expected = ['1','2','3']
        self.assertListEqual(output, expected)

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
        output = client.run_command(self.cmd, return_list=True)
        client.join(output)
        output[0].client.session.disconnect()
        self.assertRaises(SessionError, output[0].client.open_session)
        self.assertEqual(output[0].exit_code, None)

    def test_invalid_host_out(self):
        output = {'blah': None}
        self.assertRaises(ValueError, self.client.join, output)

    def test_join_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('echo me; sleep 1.5')
        try:
            client.join(output, timeout=1)
        except Timeout as ex:
            self.assertEqual(len(ex.args), 4)
            self.assertTrue(isinstance(ex.args[2], list))
            self.assertTrue(isinstance(ex.args[3], list))
        else:
            raise Exception("Expected timeout")
        self.assertFalse(output[0].channel.eof())
        client.join(output, timeout=2, consume_output=True)
        self.assertTrue(output[0].channel.eof())
        self.assertTrue(client.finished(output))

    def test_join_timeout_subset_read(self):
        hosts = [self.host, self.host]
        cmd = 'sleep %(i)s; echo %(i)s'
        host_args = [{'i': i+0.5} for i in range(len(hosts))]
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey=self.user_key)
        output = client.run_command(cmd, host_args=host_args)
        try:
            client.join(output, timeout=1)
        except Timeout as ex:
            finished_output = ex.args[2]
            unfinished_output = ex.args[3]
        else:
            raise Exception("Expected timeout")
        self.assertEqual(len(finished_output), 1)
        self.assertEqual(len(unfinished_output), 1)
        finished_stdout = list(finished_output[0].stdout)
        self.assertEqual(finished_stdout, ['0.5'])
        # Should not timeout
        client.join(unfinished_output, timeout=2)
        rest_stdout = list(unfinished_output[0].stdout)
        self.assertEqual(rest_stdout, ['1.5'])

    def test_join_timeout_set_no_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('sleep 1')
        client.join(output, timeout=2)
        self.assertTrue(client.finished(output))
        self.assertTrue(output[0].channel.eof())

    def test_read_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('sleep 2; echo me; echo me; echo me', timeout=1)
        for host_out in output:
            self.assertRaises(Timeout, list, host_out.stdout)
        self.assertFalse(output[0].channel.eof())
        client.join(output)
        for host_out in output:
            stdout = list(output[0].stdout)
            self.assertEqual(len(stdout), 3)
        self.assertTrue(output[0].channel.eof())

    def test_timeout_file_read(self):
        dir_name = os.path.dirname(__file__)
        _file = os.sep.join((dir_name, 'file_to_read'))
        contents = [b'a line\n' for _ in range(50)]
        with open(_file, 'wb') as fh:
            fh.writelines(contents)
        try:
            output = self.client.run_command('tail -f %s' % (_file,),
                                             use_pty=True,
                                             timeout=1)
            self.assertRaises(Timeout, self.client.join, output, timeout=1)
            for host_out in output:
                try:
                    for line in host_out.stdout:
                        pass
                except Timeout:
                    pass
                else:
                    raise Exception("Timeout should have been raised")
            self.assertRaises(Timeout, self.client.join, output, timeout=1)
        finally:
            os.unlink(_file)

    def test_file_read_no_timeout(self):
        try:
            xrange
        except NameError:
            xrange = range
        dir_name = os.path.dirname(__file__)
        _file = os.sep.join((dir_name, 'file_to_read'))
        contents = [b'a line\n' for _ in xrange(10000)]
        with open(_file, 'wb') as fh:
            fh.writelines(contents)
        output = self.client.run_command('cat %s' % (_file,), timeout=10)
        try:
            _out = list(output[0].stdout)
        finally:
            os.unlink(_file)
        _contents = [c.decode('utf-8').strip() for c in contents]
        self.assertEqual(len(contents), len(_out))
        self.assertListEqual(_contents, _out)

    def test_scp_send_dir(self):
        """
        Attempting to copy into a non-existent remote directory via scp_send()
        without recurse=True should raise an SCPError.
        """
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filepath = 'remote_test_dir', 'test_file_copy'
        with open(local_filename, 'w') as file_h:
            file_h.writelines([test_file_data + os.linesep])
        remote_filename = os.path.sep.join([remote_test_dir, remote_filepath])
        remote_file_abspath = os.path.expanduser('~/' + remote_filename)
        remote_test_dir_abspath = os.path.expanduser('~/' + remote_test_dir)
        try:
            cmds = self.client.scp_send(local_filename, remote_filename)
            joinall(cmds, raise_error=True)
        except Exception as ex:
            self.assertIsInstance(ex, SCPError)
        finally:
            try:
                os.unlink(local_filename)
            except OSError:
                pass
            try:
                shutil.rmtree(remote_test_dir_abspath)
            except OSError:
                pass

    def test_scp_send_dir_recurse(self):
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filepath = 'remote_test_dir', 'test_file_copy'
        with open(local_filename, 'w') as file_h:
            file_h.writelines([test_file_data + os.linesep])
        remote_filename = os.path.sep.join([remote_test_dir, remote_filepath])
        remote_file_abspath = os.path.expanduser('~/' + remote_filename)
        remote_test_dir_abspath = os.path.expanduser('~/' + remote_test_dir)
        try:
            cmds = self.client.scp_send(local_filename, remote_filename, recurse=True)
            joinall(cmds, raise_error=True)
            self.assertTrue(os.path.isdir(remote_test_dir_abspath))
            self.assertTrue(os.path.isfile(remote_file_abspath))
            remote_file_data = open(remote_file_abspath, 'r').read()
            self.assertEqual(remote_file_data.strip(), test_file_data)
        except Exception:
            raise
        finally:
            try:
                os.unlink(local_filename)
            except OSError:
                pass
            try:
                shutil.rmtree(remote_test_dir_abspath)
            except OSError:
                pass

    def test_scp_send(self):
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filepath = 'remote_test_dir', 'test_file_copy'
        with open(local_filename, 'w') as file_h:
            file_h.writelines([test_file_data + os.linesep])
        remote_file_abspath = os.path.expanduser('~/' + remote_filepath)
        cmds = self.client.scp_send(local_filename, remote_filepath)
        try:
            joinall(cmds, raise_error=True)
        except Exception:
            raise
        else:
            self.assertTrue(os.path.isfile(remote_file_abspath))
            remote_contents = open(remote_file_abspath, 'rb').read()
            local_contents = open(local_filename, 'rb').read()
            self.assertEqual(local_contents, remote_contents)
        finally:
            try:
                os.unlink(local_filename)
                os.unlink(remote_file_abspath)
            except OSError:
                pass

    def test_scp_recv_failure(self):
        cmds = self.client.scp_recv(
            'fakey fakey fake fake', 'equally fake')
        try:
            joinall(cmds, raise_error=True)
        except Exception as ex:
            self.assertEqual(ex.host, self.host)
            self.assertIsInstance(ex, SCPError)
        else:
            raise Exception("Expected SCPError, got none")

    def test_scp_recv(self):
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
        cmds = self.client.scp_recv(remote_test_path_abs, local_test_path)
        self.assertRaises(SCPError, joinall, cmds, raise_error=True)
        cmds = self.client.scp_recv(remote_test_path_abs, local_test_path,
                                    recurse=True)
        try:
            joinall(cmds, raise_error=True)
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        except Exception:
            try:
                shutil.rmtree(remote_test_path_abs)
            except Exception:
                pass
            raise
        finally:
            try:
                shutil.rmtree(local_copied_dir)
            except Exception:
                pass

        # Relative path
        cmds = self.client.scp_recv(remote_test_path_rel, local_test_path,
                                    recurse=True)
        try:
            joinall(cmds, raise_error=True)
            self.assertTrue(os.path.isdir(local_copied_dir))
            for path in local_file_paths:
                self.assertTrue(os.path.isfile(path))
        finally:
            for _path in (remote_test_path_abs, local_copied_dir):
                try:
                    shutil.rmtree(_path)
                except Exception:
                    pass

    def test_bad_hosts_value(self):
        self.assertRaises(TypeError, ParallelSSHClient, 'a host')
        self.assertRaises(TypeError, ParallelSSHClient, b'a host')

    def test_disable_agent_forward(self):
        client = ParallelSSHClient(
            [self.host], port=self.port, pkey=self.user_key,
            forward_ssh_agent=False,
            num_retries=1)
        output = client.run_command(self.cmd)
        client.join(output)
        self.assertFalse(output[0].client.forward_ssh_agent)

    def test_keepalive_off(self):
        client = ParallelSSHClient(
            [self.host], port=self.port, pkey=self.user_key,
            keepalive_seconds=0,
            num_retries=1)
        output = client.run_command(self.cmd)
        client.join(output)
        self.assertFalse(output[0].client.keepalive_seconds)

    def test_return_list_last_output_multi_host(self):
        host2, host3 = '127.0.0.2', '127.0.0.3'
        server2 = OpenSSHServer(host2, port=self.port)
        server3 = OpenSSHServer(host3, port=self.port)
        servers = [server2, server3]
        for server in servers:
            server.start_server()
        try:
            hosts = [self.host, host2, host3]
            client = ParallelSSHClient(hosts, port=self.port,
                                       pkey=self.user_key,
                                       num_retries=1)
            client.run_command(self.cmd)
            expected_exit_code = 0
            expected_stdout = [self.resp]
            expected_stderr = []
            last_out = client.get_last_output(return_list=True)
            self.assertIsInstance(last_out, list)
            self.assertEqual(len(last_out), len(hosts))
            self.assertIsInstance(last_out[0], HostOutput)
            for host_i, host_output in enumerate(last_out):
                self.assertEqual(host_output.host, client.hosts[host_i])
                self.assertEqual(host_output.exit_code, None)
                _stdout = list(host_output.stdout)
                _stderr = list(host_output.stderr)
                self.assertListEqual(expected_stdout, _stdout)
                self.assertListEqual(expected_stderr, _stderr)
                self.assertEqual(host_output.exit_code, expected_exit_code)
        finally:
            for server in servers:
                server.stop()

    def test_client_disconnect(self):
        client = ParallelSSHClient([self.host],
                                   port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1)
        output = client.run_command(self.cmd,
                                    return_list=True)
        client.join(output, consume_output=True)
        single_client = list(client._host_clients.values())[0]
        del client
        self.assertEqual(single_client.session, None)

    def test_client_disconnect_error(self):
        def disc():
            raise Exception
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key, num_retries=1)
        output = client.run_command(self.cmd)
        client.join(output)
        client._host_clients[(0, self.host)].disconnect = disc
        del client

    def test_multiple_join_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        for _ in range(5):
            output = client.run_command(self.cmd, return_list=True)
            client.join(output, timeout=1, consume_output=True)
            for host_out in output:
                self.assertTrue(host_out.client.finished(host_out.channel))
        output = client.run_command('sleep 2', return_list=True)
        self.assertRaises(Timeout, client.join, output, timeout=1, consume_output=True)
        for host_out in output:
            self.assertFalse(host_out.client.finished(host_out.channel))

    def test_multiple_run_command_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        for _ in range(5):
            output = client.run_command('pwd', return_list=True, timeout=1)
            for host_out in output:
                stdout = list(host_out.stdout)
                self.assertTrue(len(stdout) > 0)
                self.assertTrue(host_out.client.finished(host_out.channel))
        output = client.run_command('sleep 2; echo me', return_list=True, timeout=1)
        for host_out in output:
            self.assertRaises(Timeout, list, host_out.stdout)
        client.join(output)
        for host_out in output:
            stdout = list(host_out.stdout)
            self.assertEqual(stdout, ['me'])

    def read_stream_dt(self, host_out, stream, read_timeout):
        now = datetime.now()
        timed_out = False
        try:
            for line in stream:
                pass
        except Timeout:
            self.client.reset_output_generators(host_out, timeout=read_timeout)
            timed_out = True
        finally:
            dt = datetime.now() - now
            return dt, timed_out

    def test_read_timeout_mixed_output(self):
        cmd = 'sleep 1; echo start >&2; for i in 1 4 4; do sleep $i; echo $i; done'
        read_timeout = 3
        output = self.client.run_command(
            cmd, timeout=read_timeout, stop_on_errors=False, return_list=True)
        for host_out in output:
            while not host_out.client.finished(host_out.channel):
                dt, timed_out = self.read_stream_dt(host_out, host_out.stdout, read_timeout)
                dt_seconds = dt.total_seconds()
                # Timeout within timeout value + 3%
                self.assertTrue(
                    not timed_out or (read_timeout <= dt_seconds <= read_timeout*1.03),
                    msg="Read for stdout timed out at %s seconds for %s second timeout" % (
                        dt_seconds, read_timeout))
                dt, timed_out = self.read_stream_dt(host_out, host_out.stderr, read_timeout)
                dt_seconds = dt.total_seconds()
                self.assertTrue(
                    not timed_out or (read_timeout <= dt_seconds <= read_timeout*1.03),
                    msg="Read for stdout timed out at %s seconds for %s second timeout" % (
                        dt_seconds, read_timeout))

    def test_read_stdout_no_timeout(self):
        cmd = 'sleep 1; echo me; sleep 1; echo me'
        read_timeout = 3
        output = self.client.run_command(
            cmd, timeout=read_timeout, stop_on_errors=False, return_list=True)
        for host_out in output:
            dt, timed_out = self.read_stream_dt(host_out, host_out.stdout, read_timeout)
            self.assertFalse(timed_out)
            self.assertTrue(dt.total_seconds() < read_timeout)
            # Command finished, shouldn't time out
            dt, timed_out = self.read_stream_dt(host_out, host_out.stderr, read_timeout)
            self.assertFalse(timed_out)

    def test_read_timeout_no_timeouts(self):
        cmd = 'echo me; echo me_stderr >&2'
        read_timeout = 1
        # No timeouts
        output = self.client.run_command(
            cmd, timeout=read_timeout, stop_on_errors=False, return_list=True)
        for host_out in output:
            dt, timed_out = self.read_stream_dt(host_out, host_out.stdout, read_timeout)
            self.assertTrue(dt.total_seconds() < read_timeout)
            self.assertFalse(timed_out)
            dt, timed_out = self.read_stream_dt(host_out, host_out.stderr, read_timeout)
            self.assertFalse(timed_out)
            self.assertTrue(dt.total_seconds() < read_timeout)

    def test_read_stdout_timeout_stderr_no_timeout(self):
        cmd = 'sleep 1; echo me >&2; sleep 1; echo me >&2; sleep 1'
        read_timeout = 2
        # No timeouts
        output = self.client.run_command(
            cmd, timeout=read_timeout, stop_on_errors=False, return_list=True)
        for host_out in output:
            dt, timed_out = self.read_stream_dt(host_out, host_out.stdout, read_timeout)
            self.assertTrue(timed_out)
            self.assertTrue(read_timeout <= dt.total_seconds() <= read_timeout*1.03)
            dt, timed_out = self.read_stream_dt(host_out, host_out.stderr, read_timeout)
            self.assertFalse(timed_out)
            self.assertTrue(dt.total_seconds() < read_timeout)

    # TODO:
    # * forward agent enabled
    # * password auth
    # * sftp init error
    # * copy dir recurse off
    # * sftp put error
    # * scp recv file not exist
    # * scp send error opening remote file
    # * sftp get error reading remote file
