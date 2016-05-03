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


"""Unittests for :mod:`pssh.SSHClient` class"""

import gevent
import socket
import time
import shutil
import unittest
from pssh import SSHClient, ParallelSSHClient, UnknownHostException, AuthenticationException,\
     logger, ConnectionErrorException, UnknownHostException, SSHException, utils
from embedded_server.embedded_server import start_server, make_socket, logger as server_logger, \
     paramiko_logger
from embedded_server.fake_agent import FakeAgent
import paramiko
import os
from test_pssh_client import USER_KEY
import random, string
import tempfile

USER_KEY_PATH = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key'])
USER_KEY = paramiko.RSAKey.from_private_key_file(USER_KEY_PATH)

class SSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'echo me'
        self.fake_resp = 'me'
        self.user_key = USER_KEY
        self.host = '127.0.0.1'
        self.listen_socket = make_socket(self.host)
        self.listen_port = self.listen_socket.getsockname()[1]
        self.server = start_server(self.listen_socket)

    def tearDown(self):
        del self.server
        del self.listen_socket
        
    def test_ssh_client_mkdir_recursive(self):
        """Test SFTP mkdir of SSHClient"""
        base_path = 'remote_test_dir1'
        remote_dir = os.path.sep.join([base_path,
                                       'remote_test_dir2',
                                       'remote_test_dir3'])
        try:
            shutil.rmtree(base_path)
        except OSError:
            pass
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.mkdir(client._make_sftp(), remote_dir)
        self.assertTrue(os.path.isdir(remote_dir),
                        msg="SFTP recursive mkdir failed")
        shutil.rmtree(base_path)
        del client

    def test_ssh_client_mkdir_recursive_abspath(self):
        """Test SFTP mkdir of SSHClient with absolute path
        
        Absolute SFTP paths resolve under the users' home directory,
        not the root filesystem
        """
        base_path = 'tmp'
        remote_dir = os.path.sep.join([base_path,
                                       'remote_test_dir2',
                                       'remote_test_dir3'])
        try:
            shutil.rmtree(base_path)
        except OSError:
            pass
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.mkdir(client._make_sftp(), '/' + remote_dir)
        self.assertTrue(os.path.isdir(remote_dir),
                        msg="SFTP recursive mkdir failed")
        shutil.rmtree(base_path)
        del client

    def test_ssh_client_mkdir_single(self):
        """Test SFTP mkdir of SSHClient"""
        remote_dir = 'remote_test_dir1'
        try:
            shutil.rmtree(remote_dir)
        except OSError:
            pass
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.mkdir(client._make_sftp(), remote_dir)
        self.assertTrue(os.path.isdir(remote_dir),
                        msg="SFTP recursive mkdir failed")
        shutil.rmtree(remote_dir)
        del client

    def test_sftp_exceptions(self):
        self.server.kill()
        # Make socket with no server listening on it on separate ip
        host = '127.0.0.3'
        _socket = make_socket(host)
        port = _socket.getsockname()[1]
        self.assertRaises(ConnectionErrorException, SSHClient,
                          host, port=port, num_retries=1)
        del _socket
    
    def test_ssh_client_sftp(self):
        """Test SFTP features of SSHClient. Copy local filename to server,
        check that data in both files is the same, make new directory on
        server, remove files and directory."""
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_test_dir, remote_filename = 'remote_test_dir', 'test_file_copy'
        remote_filename = os.path.sep.join([remote_test_dir, remote_filename])
        remote_dir = 'remote_dir'
        test_file = open(local_filename, 'w')
        test_file.writelines([test_file_data + os.linesep])
        test_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.copy_file(local_filename, remote_filename)
        self.assertTrue(os.path.isdir(remote_test_dir),
                        msg="SFTP create remote directory failed")
        self.assertTrue(os.path.isfile(remote_filename),
                        msg="SFTP copy failed")
        copied_file = open(remote_filename, 'r')
        copied_file_data = copied_file.readlines()[0].strip()
        copied_file.close()
        self.assertEqual(test_file_data, copied_file_data,
                         msg="Data in destination file %s does \
not match source %s" % (copied_file_data, test_file_data))
        for filepath in [local_filename, remote_filename]:
            os.unlink(filepath)
        client.mkdir(client._make_sftp(), remote_dir)
        self.assertTrue(os.path.isdir(remote_dir))
        for dirpath in [remote_dir, remote_test_dir]:
            os.rmdir(dirpath)
        del client

    def test_ssh_client_local_directory(self):
        """Tests copying directories with SSH client. Copy all the files from
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
            local_file_path = os.path.join(local_test_path, 'foo' + str(i))
            remote_file_path = os.path.join(remote_test_path, 'foo' + str(i))
            remote_file_paths.append(remote_file_path)
            test_file = open(local_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.copy_file(local_test_path, remote_test_path, recurse=True)
        for path in remote_file_paths:
            self.assertTrue(os.path.isfile(path))
        shutil.rmtree(local_test_path)
        shutil.rmtree(remote_test_path)

    def test_ssh_client_copy_remote_directory(self):
        """Tests copying a remote directory to the localhost"""
        remote_test_directory = 'remote_test_dir'
        local_test_directory = 'local_test_dir'
        for path in [local_test_path, remote_test_path]:
            try:
                shutil.rmtree(path)
            except OSError:
                pass
        os.mkdir(remote_test_directory)
        test_files = []
        for i in range(0, 10):
            file_name = 'foo' + str(i)
            test_files.append(file_name)
            file_path = os.path.join(remote_test_directory, file_name)
            test_file = open(file_path, 'w')
            test_file.write('test')
            test_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.copy_file_to_local(remote_test_directory, local_test_directory, recurse=True)
        for test_file in test_files:
            file_path = os.path.join(local_test_directory, test_file)
            self.assertTrue(os.path.exists(file_path))
        shutil.rmtree(remote_test_directory)
        shutil.rmtree(local_test_directory)

    def test_ssh_client_directory_no_recurse(self):
        """Tests copying directories with SSH client. Copy all the files from
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
            local_file_path = os.path.join(local_test_path, 'foo' + str(i))
            remote_file_path = os.path.join(remote_test_path, 'foo' + str(i))
            remote_file_paths.append(remote_file_path)
            test_file = open(local_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        self.assertRaises(ValueError, client.copy_file, local_test_path, remote_test_path)
        shutil.rmtree(local_test_path)

    def test_ssh_client_sftp_from_remote(self):
        """Test copying a file from a remote host to the local host. Copy
        remote filename to local host, check that the data is intact, make a
        directory on the localhost, then delete the file and directory."""
        test_file_data = 'test'
        remote_filename = 'test_remote'
        local_test_dir, local_filename = 'local_test_dir', 'test_local'
        local_filename = os.path.join(local_test_dir, local_filename)
        remote_file = open(remote_filename, 'w')
        remote_file.write(test_file_data)
        remote_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.copy_file_to_local(remote_filename, local_filename)
        self.assertTrue(os.path.isdir(local_test_dir),
                        msg="SFTP create local directory failed")
        self.assertTrue(os.path.isfile(local_filename),
                        msg="SFTP copy failed")
        copied_file = open(local_filename, 'r')
        copied_file_data = copied_file.readlines()[0].strip()
        copied_file.close()
        self.assertEqual(test_file_data, copied_file_data,
                         msg="Data in destination file %s does \
not match source %s" % (copied_file_data, test_file_data))
        for filepath in [local_filename, remote_filename]:
            os.remove(filepath)
        os.rmdir(local_test_dir)
        del client

    def test_ssh_client_sftp_from_remote_directory(self):
        """Tests copying remote files to local directory. Copy all the files
        from the remote directory, then make sure they're all present."""
        test_file_data = 'test'
        remote_test_path = 'directory_test_remote'
        local_test_path = 'directory_test_local'
        for path in [local_test_path, remote_test_path]:
            try:
                shutil.rmtree(path)
            except OSError:
                pass
        os.mkdir(remote_test_path)
        os.mkdir(os.path.join(remote_test_path, 'subdir'))
        local_file_paths = []
        for i in range(0, 10):
            remote_file_path = os.path.join(remote_test_path, 'subdir', 'foo' + str(i))
            local_file_path = os.path.join(local_test_path, 'subdir', 'foo' + str(i))
            local_file_paths.append(local_file_path)
            test_file = open(remote_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        client.copy_file_to_local(remote_test_path, local_test_path, recurse=True)
        for path in local_file_paths:
            self.assertTrue(os.path.isfile(path))
        shutil.rmtree(local_test_path)
        shutil.rmtree(remote_test_path)

    def test_ssh_client_remote_directory_no_recurse(self):
        """Tests copying directories with SSH client. Copy all the files from
        local directory to server, then make sure they are all present."""
        test_file_data = 'test'
        remote_test_path = 'directory_test'
        local_test_path = 'directory_test_copied'
        try:
            shutil.rmtree(remote_test_path)
        except OSError:
            pass
        os.mkdir(remote_test_path)
        local_file_paths = []
        for i in range(0, 10):
            remote_file_path = os.path.join(remote_test_path, 'foo' + str(i))
            local_file_path = os.path.join(local_test_path, 'foo' + str(i))
            local_file_paths.append(local_file_path)
            test_file = open(remote_file_path, 'w')
            test_file.write(test_file_data)
            test_file.close()
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        self.assertRaises(ValueError, client.copy_file_to_local, remote_test_path, local_test_path)
        shutil.rmtree(remote_test_path)

    def test_ssh_agent_authentication(self):
        """Test authentication via SSH agent.
        Do not provide public key to use when creating SSHClient,
        instead override the client's agent with our own fake SSH agent,
        add our to key to agent and try to login to server.
        Key should be automatically picked up from the overriden agent"""
        agent = FakeAgent()
        agent.add_key(USER_KEY)
        client = SSHClient(self.host, port=self.listen_port,
                           agent=agent)
        channel, host, stdout, stderr, stdin = client.exec_command(self.fake_cmd)
        output = list(stdout)
        stderr = list(stderr)
        expected = [self.fake_resp]
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        del client

    def test_ssh_client_conn_failure(self):
        """Test connection error failure case - ConnectionErrorException"""
        self.assertRaises(ConnectionErrorException,
                          SSHClient, '127.0.0.100', port=self.listen_port,
                          pkey=self.user_key, num_retries=0)

    def test_ssh_client_retries(self):
        """Test connection error exceptions"""
        self.assertRaises(ConnectionErrorException, SSHClient, '127.0.0.100', port=self.listen_port,
                          pkey=self.user_key, num_retries=1)
        host = ''.join([random.choice(string.ascii_letters) for n in xrange(8)])
        self.assertRaises(UnknownHostException, SSHClient, host, port=self.listen_port,
                          pkey=self.user_key, num_retries=1)

    def test_ssh_client_unknown_host_failure(self):
        """Test connection error failure case - ConnectionErrorException"""
        host = ''.join([random.choice(string.ascii_letters) for n in xrange(8)])
        self.assertRaises(UnknownHostException,
                          SSHClient, host, port=self.listen_port,
                          pkey=self.user_key, num_retries=0)

    def test_ssh_client_pty(self):
        """Test that we get a new pty for our non-interactive SSH sessions"""
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        channel = client.client.get_transport().open_session()
        self.assertFalse(channel.event.is_set(),
                         msg="Got pty without requesting it")
        channel.get_pty()
        self.assertTrue(channel.event.is_set(),
                        msg="Requested pty but got none")
        channel.close()
        del channel
        del client

    def test_ssh_client_utf_encoding(self):
        """Test that unicode output works"""
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        expected = [u'é']
        cmd = u"echo 'é'"
        channel, host, stdout, stderr, stdin = client.exec_command(cmd)
        output = list(stdout)
        self.assertEqual(expected, output,
                         msg="Got unexpected unicode output %s - expected %s" % (
                             output, expected,))
        del client

    def test_ssh_client_shell(self):
        """Test that running command sans shell works as expected
        and that shell commands fail accordingly"""
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key)
        channel, host, stdout, stderr, stdin = client.exec_command(self.fake_cmd, use_shell=False)
        output = list(stdout)
        stderr = list(stderr)
        expected = []
        exit_code = channel.recv_exit_status()
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        self.assertTrue(exit_code == 127,
                        msg="Expected cmd not found error code 127, got %s instead" % (
                            exit_code,))
        channel, host, stdout, stderr, stdin = client.exec_command('id', use_shell=False)
        output = list(stdout)
        exit_code = channel.recv_exit_status()
        self.assertTrue(output,
                        msg="Got no output from cmd executed without shell")
        self.assertTrue(exit_code==0,
                        msg="Cmd executed with shell failed with error code %s" % (
                            exit_code,))
        del client

    def test_openssh_config(self):
        """Test reading and using OpenSSH config file"""
        config_file = tempfile.NamedTemporaryFile()
        _host = "127.0.0.2"
        _user = "config_user"
        _listen_socket = make_socket(_host)
        _server = start_server(_listen_socket)
        _port = _listen_socket.getsockname()[1]
        _key = USER_KEY_PATH
        content = [("""Host %s\n""" % (_host,)),
                   ("""  User %s\n""" % (_user,)),
                   ("""  Port %s\n""" % (_port,)),
                   ("""  IdentityFile %s\n""" % (_key,)),
                   ]
        config_file.writelines([s.encode('utf-8') for s in content])
        config_file.flush()
        host, user, port, pkey = utils.read_openssh_config(
            _host, config_file=config_file.name)
        client = SSHClient(_host, _openssh_config_file=config_file.name)
        config_file.close()
        self.assertEqual(host, _host)
        self.assertEqual(user, _user)
        self.assertEqual(port, _port)
        self.assertTrue(pkey)
        self.assertEqual(client.host, _host)
        self.assertEqual(client.user, _user)
        self.assertEqual(client.port, _port)
        self.assertTrue(client.pkey)
        del _server, _listen_socket

    def test_openssh_config_missing(self):
        client = SSHClient(self.host, port=self.listen_port,
                           pkey=self.user_key,
                           _openssh_config_file='fake', num_retries=1)
        self.assertTrue(client)

if __name__ == '__main__':
    unittest.main()
