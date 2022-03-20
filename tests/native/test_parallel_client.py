# -*- coding: utf-8 -*-
# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2021 Panos Kittenis
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
import string
import random
from hashlib import sha256
from datetime import datetime
from unittest.mock import patch, MagicMock

from gevent import joinall, spawn, socket, sleep, Timeout as GTimeout
from pssh.config import HostConfig
from pssh.clients.native import ParallelSSHClient
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    PKeyFileError, ShellError, HostArgumentError, NoIPv6AddressFoundError, \
    AuthenticationError
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
        self.long_cmd = lambda lines: 'for (( i=0; i<%s; i+=1 )) do echo $i; sleep .1; done' % (lines,)

    def make_random_port(self, host=None):
        host = '127.0.0.1' if host is None else host
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        listen_port = sock.getsockname()[1]
        sock.close()
        return listen_port

    def test_connect_auth(self):
        client = ParallelSSHClient([self.host], pkey=self.user_key, port=self.port, num_retries=1)
        joinall(client.connect_auth(), raise_error=True)

    def test_pkey_from_memory(self):
        with open(self.user_key, 'rb') as fh:
            key = fh.read()
        client = ParallelSSHClient([self.host], pkey=key, port=self.port, num_retries=1)
        joinall(client.connect_auth(), raise_error=True)

    def test_client_shells(self):
        shells = self.client.open_shell()
        self.client.run_shell_commands(shells, self.cmd)
        self.client.run_shell_commands(shells, [self.cmd, self.cmd])
        self.client.run_shell_commands(
            shells, """
            %s
            exit 1
            """ % (self.cmd,))
        self.client.join_shells(shells)
        self.assertRaises(ShellError, self.client.run_shell_commands, shells, self.cmd)
        for shell in shells:
            stdout = list(shell.stdout)
            self.assertListEqual(stdout, [self.resp, self.resp, self.resp, self.resp])
            expected_exit_code = 1
            self.assertEqual(shell.exit_code, expected_exit_code)
            self.assertListEqual(list(shell.stderr), [])
            self.assertTrue(shell.stdin is not None)

    def test_client_shells_read_timeout(self):
        shells = self.client.open_shell(read_timeout=.1)
        self.client.run_shell_commands(shells, self.cmd)
        self.client.run_shell_commands(shells, [self.cmd, 'sleep .25', 'exit 1'])
        stdout = []
        for shell in shells:
            try:
                for line in shell.output.stdout:
                    stdout.append(line)
            except Timeout:
                pass
            self.assertListEqual(stdout, [self.resp, self.resp])
            self.assertEqual(shell.output.exit_code, None)
            expected_exit_code = 1
            self.client.join_shells(shells)
            self.assertEqual(shell.output.exit_code, expected_exit_code)

    def test_client_shells_timeout(self):
        client = ParallelSSHClient([self.host], pkey=self.user_key, port=self.port,
                                   timeout=0.01, num_retries=1)
        client._make_ssh_client = MagicMock()
        client._make_ssh_client.side_effect = Timeout
        self.assertRaises(Timeout, client.open_shell)

    def test_client_shells_join_timeout(self):
        shells = self.client.open_shell()
        cmd = """
        echo me
        sleep .3
        echo me
        """
        self.client.run_shell_commands(shells, cmd)
        self.assertRaises(Timeout, self.client.join_shells, shells, timeout=.1)
        try:
            self.client.join_shells(shells, timeout=.1)
        except Timeout:
            pass
        else:
            raise AssertionError
        self.client.join_shells(shells, timeout=1)
        stdout = list(shells[0].stdout)
        self.assertListEqual(stdout, [self.resp, self.resp])

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
        self.assertIsNone(self.client._join(None))
        self.assertIsNone(self.client.join([None]))

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
        output = self.client.run_command('exit 1')
        expected_exit_code = 1
        self.client.join(output)
        exit_code = output[0].exit_code
        self.assertEqual(expected_exit_code, exit_code,
                         msg="Got unexpected exit code - %s, expected %s" %
                         (exit_code,
                          expected_exit_code,))

    def test_pssh_client_no_stdout_non_zero_exit_code_immediate_exit_no_join(self):
        output = self.client.run_command('exit 1')
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
                                   pkey=self.user_key,
                                   timeout=1,
                                   retry_delay=.1,
                                   )
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
        self.assertEqual(output[1].host, hosts[1])
        self.assertIsInstance(output[1].exception, ConnectionErrorException)

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

    def test_timeout_on_open_session(self):
        timeout = .1
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key,
                                   timeout=timeout,
                                   num_retries=1)
        def _session(timeout=None):
            sleep(.2)
        joinall(client.connect_auth())
        sleep(.01)
        client._host_clients[(0, self.host)].open_session = _session
        self.assertRaises(Timeout, client.run_command, self.cmd)

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
        cmd = spawn(client.run_command, 'sleep .1', stop_on_errors=False)
        output = cmd.get(timeout=.3)
        self.assertTrue(output[0].exception is None)

    def test_pssh_client_long_running_command_exit_codes(self):
        expected_lines = 2
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.assertIsNone(output[0].exit_code)
        self.assertFalse(self.client.finished(output))
        self.client.join(output, consume_output=True)
        self.assertTrue(self.client.finished(output))
        self.assertEqual(output[0].exit_code, 0)
        stdout = list(output[0].stdout)
        self.assertEqual(len(stdout), 0)

    def test_pssh_client_long_running_command_exit_codes_no_stdout(self):
        expected_lines = 2
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.assertEqual(len(output), len(self.client.hosts))
        self.assertIsNone(output[0].exit_code)
        self.assertFalse(self.client.finished(output))
        self.client.join(output)
        self.assertTrue(self.client.finished(output))
        self.assertEqual(output[0].exit_code, 0)
        stdout = list(output[0].stdout)
        self.assertEqual(expected_lines, len(stdout))

    def test_pssh_client_retries(self):
        """Test connection error retries"""
        # listen_port = self.make_random_port()
        expected_num_tries = 2
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=b"fake",
                                   num_retries=expected_num_tries,
                                   retry_delay=.1,
                                   )
        self.assertRaises(AuthenticationError, client.run_command, 'blah')
        try:
            client.run_command('blah')
        except AuthenticationError as ex:
            max_tries = ex.args[-2:][0]
            num_tries = ex.args[-1:][0]
            self.assertEqual(expected_num_tries, max_tries)
            self.assertEqual(expected_num_tries, num_tries)
        else:
            raise Exception('No AuthenticationError')

    def test_sftp_exceptions(self):
        # Port with no server listening on it on separate ip
        port = self.make_random_port(host=self.host)
        client = ParallelSSHClient([self.host], port=port, num_retries=1)
        _local = "fake_local"
        _remote = "fake_remote"
        cmds = client.copy_file(_local, _remote)
        client.pool.join()
        for cmd in cmds:
            try:
                cmd.get()
            except Exception as ex:
                self.assertEqual(ex.args[2], self.host)
                self.assertEqual(ex.args[3], port)
                self.assertIsInstance(ex, ConnectionErrorException)
            else:
                raise Exception("Expected ConnectionErrorException, got none")
        self.assertFalse(os.path.isfile(_local))
        self.assertFalse(os.path.isfile(_remote))

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
            self.assertEqual(ex.args[2], self.host)
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
        # Run again without re-assigning host list, should run the same
        output = client.run_command(self.cmd)
        self.assertEqual(len(output), len(hosts))
        # Re-assigning host list with new hosts should also work
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
        output = client.run_command(self.cmd, stop_on_errors=False)
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

    def test_connection_error(self):
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
        self.assertIsInstance(output[0].exception, ConnectionError)

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
            self.assertEqual(output[1].host, hosts[1][0])
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
            self.assertEqual(output[1].host, hosts[1][0])
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
        self.assertRaises(ValueError, ParallelSSHClient, iter(hosts), host_config=host_config)

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
        client.join()
        for i, host in enumerate(hosts):
            expected = [host_args[i]]
            stdout = list(output[i].stdout)
            self.assertEqual(expected, stdout)
            self.assertEqual(output[i].exit_code, 0)
        host_args = (('arg1', 'arg2'), ('arg3', 'arg4'), ('arg5', 'arg6'),)
        cmd = 'echo %s %s'
        output = client.run_command(cmd, host_args=host_args)
        client.join()
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

    def test_run_command_encoding(self):
        """Test that unicode command works"""
        exp = b"\xbc"
        _cmd = b"echo " + exp
        cmd = _cmd.decode('latin-1')
        expected = [exp.decode('latin-1')]
        output = self.client.run_command(cmd, encoding='latin-1')
        stdout = list(output[0].stdout)
        self.assertEqual(expected, stdout)
        # With join
        output = self.client.run_command(cmd, encoding='latin-1')
        self.client.join(output)
        stdout = list(output[0].stdout)
        self.assertEqual(expected, stdout)

    def test_shell_encoding(self):
        exp = b"\xbc"
        _cmd = b"echo " + exp
        cmd = _cmd.decode('latin-1')
        expected = [exp.decode('latin-1')]
        shells = self.client.open_shell(encoding='latin-1')
        self.client.run_shell_commands(shells, cmd)
        self.client.join_shells(shells)
        stdout = list(shells[0].stdout)
        self.assertEqual(expected, stdout)

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

    def test_conn_failure(self):
        """Test connection error failure case - ConnectionErrorException"""
        client = ParallelSSHClient(['127.0.0.100'], port=self.port,
                                   num_retries=0)
        self.assertRaises(ConnectionErrorException,
                          client.run_command, self.cmd)

    def test_retries(self):
        client = ParallelSSHClient(['127.0.0.100'], port=self.port,
                                   num_retries=2, retry_delay=.1)
        self.assertRaises(ConnectionErrorException, client.run_command, self.cmd)
        host = ''.join([random.choice(string.ascii_letters) for n in range(8)])
        client.hosts = [host]
        self.assertRaises(UnknownHostException, client.run_command, self.cmd)

    def test_setting_hosts(self):
        host2 = '127.0.0.3'
        server2 = OpenSSHServer(host2, port=self.port)
        server2.start_server()
        client = ParallelSSHClient(
            [self.host], port=self.port,
            num_retries=1, retry_delay=1,
            pkey=self.user_key,
        )
        joinall(client.connect_auth())
        _client = list(client._host_clients.values())[0]
        client.hosts = [self.host]
        joinall(client.connect_auth())
        try:
            self.assertEqual(len(client._host_clients), 1)
            _client_after = list(client._host_clients.values())[0]
            self.assertEqual(id(_client), id(_client_after))
            client.hosts = ['127.0.0.2', self.host, self.host]
            self.assertEqual(len(client._host_clients), 0)
            joinall(client.connect_auth())
            self.assertEqual(len(client._host_clients), 2)
            client.hosts = ['127.0.0.2', self.host, self.host]
            self.assertListEqual([(1, self.host), (2, self.host)],
                                 sorted(list(client._host_clients.keys())))
            self.assertEqual(len(client._host_clients), 2)
            hosts = [self.host, self.host, host2]
            client.hosts = hosts
            joinall(client.connect_auth())
            self.assertListEqual([(0, self.host), (1, self.host), (2, host2)],
                                 sorted(list(client._host_clients.keys())))
            self.assertEqual(len(client._host_clients), 3)
            hosts = [host2, self.host, self.host]
            client.hosts = hosts
            joinall(client.connect_auth())
            self.assertListEqual([(0, host2), (1, self.host), (2, self.host)],
                                 sorted(list(client._host_clients.keys())))
            self.assertEqual(len(client._host_clients), 3)
            client.hosts = [self.host]
            self.assertEqual(len(client._host_clients), 0)
            joinall(client.connect_auth())
            self.assertEqual(len(client._host_clients), 1)
            client.hosts = [self.host, host2]
            joinall(client.connect_auth())
            self.assertListEqual([(0, self.host), (1, host2)],
                                 sorted(list(client._host_clients.keys())))
            self.assertEqual(len(client._host_clients), 2)
            try:
                client.hosts = None
            except ValueError:
                pass
            else:
                raise AssertionError
            try:
                client.hosts = ''
            except TypeError:
                pass
            else:
                raise AssertionError
        finally:
            server2.stop()

    def test_unknown_host_failure(self):
        """Test connection error failure case - ConnectionErrorException"""
        host = ''.join([random.choice(string.ascii_letters) for n in range(8)])
        client = ParallelSSHClient([host], port=self.port,
                                   num_retries=1)
        self.assertRaises(UnknownHostException, client.run_command, self.cmd)

    def test_invalid_host_out(self):
        output = {'blah': None}
        self.assertRaises(ValueError, self.client.join, output)

    def test_join_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('echo me; sleep .5')
        try:
            client.join(output, timeout=.1)
        except Timeout as ex:
            self.assertEqual(len(ex.args), 4)
            self.assertTrue(isinstance(ex.args[2], list))
            self.assertTrue(isinstance(ex.args[3], list))
        else:
            raise Exception("Expected timeout")
        self.assertFalse(output[0].channel.eof())
        client.join(output, timeout=2, consume_output=False)
        self.assertTrue(output[0].channel.eof())
        self.assertTrue(client.finished(output))
        stdout = list(output[0].stdout)
        self.assertListEqual(stdout, [self.resp])

    def test_join_timeout_subset_read(self):
        hosts = [self.host, self.host]
        cmd = 'sleep %(i)s; echo %(i)s'
        host_args = [{'i': '0.1'},
                     {'i': '0.25'},
                     ]
        client = ParallelSSHClient(hosts, port=self.port,
                                   pkey=self.user_key)
        output = client.run_command(cmd, host_args=host_args)
        try:
            client.join(output, timeout=.2)
        except Timeout as ex:
            finished_output = ex.args[2]
            unfinished_output = ex.args[3]
        else:
            raise Exception("Expected timeout")
        self.assertEqual(len(finished_output), 1)
        self.assertEqual(len(unfinished_output), 1)
        finished_stdout = list(finished_output[0].stdout)
        self.assertEqual(finished_stdout, ['0.1'])
        # Should not timeout
        client.join(unfinished_output, timeout=2)
        rest_stdout = list(unfinished_output[0].stdout)
        self.assertEqual(rest_stdout, ['0.25'])

    def test_join_timeout_set_no_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('sleep .1')
        client.join(output, timeout=.5)
        self.assertTrue(client.finished(output))

    def test_read_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('sleep .3; echo me; echo me; echo me', read_timeout=.2)
        for host_out in output:
            self.assertRaises(Timeout, list, host_out.stdout)
        self.assertFalse(client.finished(output))
        client.join(output)
        # import ipdb; ipdb.set_trace()
        for host_out in output:
            stdout = list(output[0].stdout)
            self.assertEqual(len(stdout), 3)
        self.assertTrue(client.finished(output))

    def test_partial_read_timeout_close_cmd(self):
        self.assertTrue(self.client.finished())
        output = self.client.run_command('while true; do echo a line; sleep .1; done',
                                         use_pty=True, read_timeout=.15)
        stdout = []
        try:
            with GTimeout(seconds=.25):
                for line in output[0].stdout:
                    stdout.append(line)
        except Timeout:
            pass
        self.assertTrue(len(stdout) > 0)
        output[0].client.close_channel(output[0].channel)
        self.client.join(output)
        # Should not timeout
        with GTimeout(seconds=.5):
            stdout = list(output[0].stdout)
        self.assertTrue(len(stdout) > 0)

    def test_partial_read_timeout_join_no_output(self):
        self.assertTrue(self.client.finished())
        self.client.run_command('while true; do echo a line; sleep .1; done')
        try:
            with GTimeout(seconds=.1):
                self.client.join()
        except GTimeout:
            pass
        else:
            raise Exception("Should have timed out")
        output = self.client.get_last_output()
        stdout = []
        try:
            with GTimeout(seconds=.1):
                for line in output[0].stdout:
                    stdout.append(line)
        except GTimeout:
            pass
        else:
            raise Exception("Should have timed out")
        self.assertTrue(len(stdout) > 0)
        self.assertRaises(Timeout, self.client.join, timeout=.1)
        stdout = []
        try:
            with GTimeout(seconds=.2):
                for line in output[0].stdout:
                    stdout.append(line)
        except GTimeout:
            pass
        else:
            raise Exception("Should have timed out")
        self.assertTrue(len(stdout) > 0)
        # Setting timeout
        output[0].read_timeout = .2
        stdout = []
        try:
            for line in output[0].stdout:
                stdout.append(line)
        except Timeout:
            pass
        else:
            raise Exception("Should have timed out")
        self.assertTrue(len(stdout) > 0)
        output[0].client.close_channel(output[0].channel)
        self.client.join()
        self.assertTrue(self.client.finished())
        stdout = list(output[0].stdout)
        self.assertTrue(len(stdout) > 0)

    def test_timeout_file_read(self):
        dir_name = os.path.dirname(__file__)
        _file = os.sep.join((dir_name, 'file_to_read'))
        contents = [b'a line\n' for _ in range(50)]
        with open(_file, 'wb') as fh:
            fh.writelines(contents)
        try:
            output = self.client.run_command('tail -f %s' % (_file,),
                                             use_pty=True,
                                             read_timeout=.1)
            self.assertRaises(Timeout, self.client.join, output, timeout=.1)
            for host_out in output:
                try:
                    for line in host_out.stdout:
                        pass
                except Timeout:
                    pass
                else:
                    raise Exception("Timeout should have been raised")
            self.assertRaises(Timeout, self.client.join, output, timeout=.1)
        finally:
            os.unlink(_file)

    def test_file_read_no_timeout(self):
        dir_name = os.path.dirname(__file__)
        _file = os.sep.join((dir_name, 'file_to_read'))
        contents = [b'a line\n' for _ in range(1000)]
        with open(_file, 'wb') as fh:
            fh.writelines(contents)
        try:
            output = self.client.run_command('cat %s' % (_file,), read_timeout=10)
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
            sleep(.1)
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

    def test_scp_send_larger_files(self):
        hosts = ['127.0.0.1%s' % (i,) for i in range(1, 3)]
        servers = [OpenSSHServer(host, port=self.port) for host in hosts]
        for server in servers:
            server.start_server()
        client = ParallelSSHClient(
            hosts, port=self.port, pkey=self.user_key, num_retries=1, timeout=1,
            pool_size=len(hosts),
        )
        local_filename = 'test_file'
        remote_filepath = 'file_copy'
        copy_args = [{
            'local_file': local_filename,
            'remote_file': 'host_%s_%s' % (n, remote_filepath)}
                     for n in range(len(hosts))]
        remote_file_names = [arg['remote_file'] for arg in copy_args]
        sha = sha256()
        with open(local_filename, 'wb') as file_h:
            for _ in range(10000):
                data = os.urandom(1024)
                file_h.write(data)
                sha.update(data)
        source_file_sha = sha.hexdigest()
        sha = sha256()
        cmds = client.scp_send('%(local_file)s', '%(remote_file)s', copy_args=copy_args)
        try:
            joinall(cmds, raise_error=True)
        except Exception:
            raise
        else:
            del client
            for remote_file_name in remote_file_names:
                remote_file_abspath = os.path.expanduser('~/' + remote_file_name)
                self.assertTrue(os.path.isfile(remote_file_abspath))
                with open(remote_file_abspath, 'rb') as remote_fh:
                    data = remote_fh.read(10240)
                    while data:
                        sha.update(data)
                        data = remote_fh.read(10240)
                remote_file_sha = sha.hexdigest()
                sha = sha256()
                self.assertEqual(source_file_sha, remote_file_sha)
        finally:
            try:
                os.unlink(local_filename)
                for remote_file_name in remote_file_names:
                    remote_file_abspath = os.path.expanduser('~/' + remote_file_name)
                    os.unlink(remote_file_abspath)
            except OSError:
                pass

    def test_scp_bad_copy_args(self):
        client = ParallelSSHClient([self.host, self.host])
        copy_args = [{'local_file': 'fake_file', 'remote_file': 'fake_remote_file'}]
        self.assertRaises(HostArgumentException,
                          client.scp_send, '%(local_file)s', '%(remote_file)s',
                          copy_args=copy_args)
        self.assertRaises(HostArgumentError,
                          client.scp_recv, '%(local_file)s', '%(remote_file)s',
                          copy_args=copy_args)
        self.assertFalse(os.path.isfile('fake_file'))
        self.assertFalse(os.path.isfile('fake_remote_file'))

    def test_scp_send_exc(self):
        client = ParallelSSHClient([self.host], pkey=self.user_key, num_retries=1)
        def _scp_send(*args):
            raise Exception
        def _client_send(*args):
            return client._handle_greenlet_exc(_scp_send, 'fake')
        client._scp_send = _client_send
        cmds = client.scp_send('local_file', 'remote_file')
        self.assertRaises(Exception, joinall, cmds, raise_error=True)

    def test_scp_recv_exc(self):
        client = ParallelSSHClient([self.host], pkey=self.user_key, num_retries=1)
        def _scp_recv(*args):
            raise Exception
        def _client_recv(*args):
            return client._handle_greenlet_exc(_scp_recv, 'fake')
        client._scp_recv = _client_recv
        cmds = client.scp_recv('remote_file', 'local_file')
        self.assertRaises(Exception, joinall, cmds, raise_error=True)

    def test_scp_recv_failure(self):
        cmds = self.client.scp_recv(
            'fakey fakey fake fake', 'equally fake')
        try:
            joinall(cmds, raise_error=True)
        except Exception as ex:
            self.assertEqual(ex.args[2], self.host)
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

    def test_scp_recv_larger_files(self):
        hosts = ['127.0.0.1%s' % (i,) for i in range(1, 3)]
        servers = [OpenSSHServer(host, port=self.port) for host in hosts]
        for server in servers:
            server.start_server()
        client = ParallelSSHClient(
            hosts, port=self.port, pkey=self.user_key, num_retries=1, timeout=1,
            pool_size=len(hosts),
        )
        dir_name = os.path.dirname(__file__)
        remote_filename = 'test_file'
        remote_filepath = os.path.join(dir_name, remote_filename)
        local_filename = 'file_copy'
        copy_args = [{
            'remote_file': remote_filepath,
            'local_file': os.path.expanduser("~/" + 'host_%s_%s' % (n, local_filename))}
            for n in range(len(hosts))
        ]
        local_file_names = [
            arg['local_file'] for arg in copy_args]
        sha = sha256()
        with open(remote_filepath, 'wb') as file_h:
            for _ in range(10000):
                data = os.urandom(1024)
                file_h.write(data)
                sha.update(data)
            file_h.flush()
        source_file_sha = sha.hexdigest()
        sha = sha256()
        cmds = client.scp_recv('%(remote_file)s', '%(local_file)s', copy_args=copy_args)
        try:
            joinall(cmds, raise_error=True)
        except Exception:
            raise
        else:
            del client
            for _local_file_name in local_file_names:
                self.assertTrue(os.path.isfile(_local_file_name))
                with open(_local_file_name, 'rb') as fh:
                    data = fh.read(10240)
                    while data:
                        sha.update(data)
                        data = fh.read(10240)
                local_file_sha = sha.hexdigest()
                sha = sha256()
                self.assertEqual(source_file_sha, local_file_sha)
        finally:
            try:
                os.unlink(remote_filepath)
                for _local_file_name in local_file_names:
                    os.unlink(_local_file_name)
            except OSError:
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
            self.assertTrue(client.cmds is None)
            self.assertTrue(client.get_last_output() is None)
            client.run_command(self.cmd)
            expected_stdout = [self.resp]
            expected_stderr = []
            output = client.get_last_output()
            self.assertIsInstance(output, list)
            self.assertEqual(len(output), len(hosts))
            self.assertIsInstance(output[0], HostOutput)
            client.join(output)
            for i, host in enumerate(hosts):
                self.assertEqual(output[i].host, host)
                exit_code = output[i].exit_code
                _stdout = list(output[i].stdout)
                _stderr = list(output[i].stderr)
                self.assertEqual(exit_code, 0)
                self.assertListEqual(expected_stdout, _stdout)
                self.assertListEqual(expected_stderr, _stderr)
        finally:
            for server in servers:
                server.stop()

    def test_client_disconnect(self):
        client = ParallelSSHClient([self.host],
                                   port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1)
        client.run_command(self.cmd)
        client.join(consume_output=True)
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
            output = client.run_command(self.cmd)
            client.join(output, timeout=1, consume_output=True)
            for host_out in output:
                self.assertTrue(host_out.client.finished(host_out.channel))
        output = client.run_command('sleep .2')
        self.assertRaises(Timeout, client.join, output, timeout=.1, consume_output=True)
        for host_out in output:
            self.assertFalse(host_out.client.finished(host_out.channel))

    def test_multiple_run_command_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        for _ in range(5):
            output = client.run_command('pwd', read_timeout=1)
            for host_out in output:
                stdout = list(host_out.stdout)
                self.assertTrue(len(stdout) > 0)
                self.assertTrue(host_out.client.finished(host_out.channel))
        output = client.run_command('sleep .25; echo me', read_timeout=.1)
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
            timed_out = True
        finally:
            dt = datetime.now() - now
            return dt, timed_out

    def test_read_timeout_mixed_output(self):
        cmd = 'sleep .1; echo start >&2; for i in 1 4 4; do sleep .$i; echo $i; done'
        read_timeout = .3
        output = self.client.run_command(
            cmd, read_timeout=read_timeout, stop_on_errors=False)
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
        cmd = 'sleep .1; echo me; sleep .1; echo me'
        read_timeout = 1
        output = self.client.run_command(
            cmd, read_timeout=read_timeout, stop_on_errors=False)
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
            cmd, read_timeout=read_timeout, stop_on_errors=False)
        for host_out in output:
            dt, timed_out = self.read_stream_dt(host_out, host_out.stdout, read_timeout)
            self.assertTrue(dt.total_seconds() < read_timeout)
            self.assertFalse(timed_out)
            dt, timed_out = self.read_stream_dt(host_out, host_out.stderr, read_timeout)
            self.assertFalse(timed_out)
            self.assertTrue(dt.total_seconds() < read_timeout)

    def test_read_stdout_timeout_stderr_no_timeout(self):
        """No timeouts for stderr only"""
        cmd = 'sleep .1; echo me >&2; sleep .1; echo me >&2; sleep .1'
        read_timeout = .25
        output = self.client.run_command(
            cmd, read_timeout=read_timeout, stop_on_errors=False)
        for host_out in output:
            dt, timed_out = self.read_stream_dt(host_out, host_out.stdout, read_timeout)
            self.assertTrue(timed_out)
            self.assertTrue(read_timeout <= dt.total_seconds() <= read_timeout*1.03)
            dt, timed_out = self.read_stream_dt(host_out, host_out.stderr, read_timeout)
            self.assertFalse(timed_out)
            self.assertTrue(dt.total_seconds() < read_timeout)

    def test_read_multi_same_hosts(self):
        hosts = [self.host, self.host]
        outputs = [
            self.client.run_command(self.cmd),
            self.client.run_command(self.cmd),
        ]
        for output in outputs:
            for host_out in output:
                stdout = list(host_out.stdout)
                self.assertListEqual(stdout, [self.resp])

    @patch('pssh.clients.base.single.socket')
    def test_ipv6(self, gsocket):
        hosts = ['::1']
        client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key, num_retries=1)
        addr_info = ('::1', self.port, 0, 0)
        gsocket.IPPROTO_TCP = socket.IPPROTO_TCP
        gsocket.socket = MagicMock()
        _sock = MagicMock()
        gsocket.socket.return_value = _sock
        sock_con = MagicMock()
        _sock.connect = sock_con
        getaddrinfo = MagicMock()
        gsocket.getaddrinfo = getaddrinfo
        getaddrinfo.return_value = [(
            socket.AF_INET6, socket.SocketKind.SOCK_STREAM, socket.IPPROTO_TCP, '', addr_info)]
        output = client.run_command(self.cmd, stop_on_errors=False)
        for host_out in output:
            self.assertEqual(hosts[0], host_out.host)
            self.assertIsInstance(host_out.exception, TypeError)

    def test_no_ipv6(self):
        client = ParallelSSHClient([self.host], port=self.port, pkey=self.user_key, num_retries=1, ipv6_only=True)
        output = client.run_command(self.cmd, stop_on_errors=False)
        for host_out in output:
            self.assertEqual(self.host, host_out.host)
            self.assertIsInstance(host_out.exception, NoIPv6AddressFoundError)

    # TODO:
    # * password auth
