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


"""Unittests for :mod:`pssh.SSHClient` class"""

import gevent
import socket
import time
import shutil
import unittest
from pssh import SSHClient, ParallelSSHClient, UnknownHostException, AuthenticationException,\
     logger, ConnectionErrorException, UnknownHostException, SSHException
from embedded_server.embedded_server import start_server, make_socket, logger as server_logger, \
     paramiko_logger
from embedded_server.fake_agent import FakeAgent
import paramiko
import os
from test_pssh_client import USER_KEY
import random, string
import shutil

USER_KEY = paramiko.RSAKey.from_private_key_file(
    os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key']))

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

    def test_ssh_client_directory(self):
        """Tests copying directories with SSH client. Copy all the files from
        local directory to server, then make sure they are all present."""
        test_file_data = 'test'
        local_test_path = 'directory_test'
        remote_test_path = 'directory_test_copied'
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

    def test_ssh_agent_authentication(self):
        """Test authentication via SSH agent.
        Do not provide public key to use when creating SSHClient,
        instead override the client's agent with our own fake SSH agent,
        add our to key to agent and try to login to server.
        Key should be automatically picked up from the overriden agent"""
        agent = FakeAgent()
        agent.add_key(USER_KEY)
        client = SSHClient(self.host, port=self.listen_port,
                           _agent=agent)
        channel, host, stdout, stderr = client.exec_command(self.fake_cmd)
        channel.close()
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

if __name__ == '__main__':
    unittest.main()
