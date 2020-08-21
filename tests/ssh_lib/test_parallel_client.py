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
from datetime import datetime
from sys import version_info

from gevent import joinall, spawn, Greenlet
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError, PKeyFileError
from pssh import logger as pssh_logger
from pssh.clients.ssh_lib.parallel import ParallelSSHClient

from ..embedded_server.embedded_server import make_socket
from ..embedded_server.openssh import OpenSSHServer
from .base_ssh_case import PKEY_FILENAME, PUB_FILE


pssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class LibSSHParallelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.host = '127.0.0.1'
        cls.port = 2422
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
        exit_code = output[self.host].exit_code
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

    def test_get_last_output(self):
        host = '127.0.0.9'
        server = OpenSSHServer(listen_ip=host, port=self.port)
        server.start_server()
        try:
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
        finally:
            server.stop()

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
        output = self.client.run_command(self.cmd)
        expected_exit_code = 0
        expected_stdout = [self.resp]
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

    def test_pssh_client_run_command_get_output_explicit(self):
        out = self.client.run_command(self.cmd)
        cmds = [cmd for host in out for cmd in [out[host]['cmd']]]
        output = {}
        for cmd in cmds:
            self.client.get_output(cmd, output)
        expected_exit_code = 0
        expected_stdout = [self.resp]
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
        stdout = list(output[self.host].stdout)
        self.client.join(output)
        self.assertTrue(len(stdout) == expected_lines,
                        msg="Expected %s lines of response, got %s" % (
                            expected_lines, len(stdout)))

    def test_pssh_client_auth_failure(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   user='FAKE USER',
                                   pkey=self.user_key,
                                   num_retries=1)
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
        self.assertEqual(output[hosts[1]].exception.host, hosts[1])
        try:
            raise output[hosts[1]]['exception']
        except ConnectionErrorException:
            pass
        else:
            raise Exception("Expected ConnectionError, got %s instead" % (
                output[hosts[1]]['exception'],))

    def test_pssh_client_timeout(self):
        # 1ms timeout
        client_timeout = 0.00001
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key,
                                   timeout=client_timeout,
                                   num_retries=1)
        now = datetime.now()
        output = client.run_command('sleep 1', stop_on_errors=False)
        dt = datetime.now() - now
        print("Run command took %s" % (dt,))
        self.assertIsInstance(output[self.host].exception,
                              Timeout)

    def test_connection_timeout(self):
        client_timeout = .01
        host = 'fakehost.com'
        client = ParallelSSHClient([host], port=self.port,
                                   pkey=self.user_key,
                                   timeout=client_timeout,
                                   num_retries=1)
        cmd = spawn(client.run_command, 'sleep 1', stop_on_errors=False)
        output = cmd.get(timeout=client_timeout * 200)
        self.assertIsInstance(output[host].exception,
                              ConnectionErrorException)

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
        self.assertTrue(output[self.host].exception is None)

    def test_pssh_client_long_running_command_exit_codes(self):
        expected_lines = 2
        output = self.client.run_command(self.long_cmd(expected_lines))
        self.assertTrue(self.host in output, msg="Got no output for command")
        self.assertTrue(not output[self.host].exit_code,
                        msg="Got exit code %s for still running cmd.." % (
                            output[self.host].exit_code,))
        self.assertFalse(self.client.finished(output))
        self.client.join(output, consume_output=True)
        self.assertTrue(self.client.finished(output))
        self.assertEqual(output[self.host].exit_code, 0)

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
        stdout = list(output[self.host].stdout)
        expected = 'me and me'
        self.assertTrue(len(stdout)==1,
                        msg="Got incorrect number of lines in output - %s" % (stdout,))
        self.assertEqual(output[self.host].exit_code, 0)
        self.assertEqual(expected, stdout[0],
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout[0],))

    def test_backtics_in_cmd(self):
        """Test running command with backtics in it"""
        output = self.client.run_command("out=`ls` && echo $out")
        self.client.join(output)
        self.assertEqual(output[self.host].exit_code, 0)

    def test_multiple_shell_commands(self):
        """Test running multiple shell commands in one go"""
        output = self.client.run_command("echo me; echo and; echo me")
        stdout = list(output[self.host]['stdout'])
        expected = ["me", "and", "me"]
        self.assertEqual(output[self.host].exit_code, 0)
        self.assertEqual(expected, stdout,
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout,))

    def test_escaped_quotes(self):
        """Test escaped quotes in shell variable are handled correctly"""
        output = self.client.run_command('t="--flags=\\"this\\""; echo $t')
        stdout = list(output[self.host]['stdout'])
        expected = ['--flags="this"']
        self.assertEqual(output[self.host].exit_code, 0)
        self.assertEqual(expected, stdout,
                         msg="Got unexpected output. Expected %s, got %s" % (
                             expected, stdout,))

    def test_read_timeout(self):
        client = ParallelSSHClient([self.host], port=self.port,
                                   pkey=self.user_key)
        output = client.run_command('sleep 2; echo me; echo me; echo me', timeout=1)
        for host, host_out in output.items():
            self.assertRaises(Timeout, list, host_out.stdout)
        self.assertFalse(output[self.host].channel.is_eof())
        client.join(output)
        for host, host_out in output.items():
            stdout = list(output[self.host].stdout)
            self.assertEqual(len(stdout), 3)
        self.assertTrue(output[self.host].channel.is_eof())

    def test_timeout_file_read(self):
        dir_name = os.path.dirname(__file__)
        _file = os.sep.join((dir_name, 'file_to_read'))
        contents = [b'a line\n' for _ in range(50)]
        with open(_file, 'wb') as fh:
            fh.writelines(contents)
        try:
            output = self.client.run_command(
                'tail -f %s' % (_file,), use_pty=True, timeout=5)
            self.assertRaises(Timeout, self.client.join, output, timeout=1)
            for host, host_out in output.items():
                try:
                    for line in host_out.stdout:
                        pass
                except Timeout:
                    pass
                else:
                    raise Exception("Timeout should have been raised")
            self.assertRaises(Timeout, self.client.join, output, timeout=1)
            channel = output[self.host].channel
            self.client.host_clients[self.host].close_channel(channel)
            self.client.join(output)
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
            _out = list(output[self.client.hosts[0]].stdout)
        finally:
            os.unlink(_file)
        _contents = [c.decode('utf-8').strip() for c in contents]
        self.assertEqual(len(contents), len(_out))
        self.assertListEqual(_contents, _out)
