#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
from pssh import SSHClient, ParallelSSHClient, UnknownHostException, AuthenticationException, _setup_logger, logger
from fake_server.fake_server import start_server, make_socket, logger as server_logger, \
    paramiko_logger
import os
from test_pssh_client import USER_KEY

# _setup_logger(server_logger)
# _setup_logger(logger)
# _setup_logger(paramiko_logger)

class SSHClientTest(unittest.TestCase):
    
    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'
        self.user_key = USER_KEY
        self.listen_socket = make_socket('127.0.0.1')
        self.listen_port = self.listen_socket.getsockname()[1]

    def test_ssh_client_sftp(self):
        """Test SFTP features of SSHClient. Copy local filename to server,
        check that data in both files is the same, make new directory on
        server, remove files and directory."""
        test_file_data = 'test'
        local_filename = 'test_file'
        remote_filename = 'test_file_copy'
        remote_dir = 'remote_dir'
        test_file = open(local_filename, 'w')
        test_file.writelines([test_file_data + os.linesep])
        test_file.close()
        server = start_server({ self.fake_cmd : self.fake_resp },
                              self.listen_socket)
        client = SSHClient('127.0.0.1', port=self.listen_port,
                           pkey=self.user_key)
        client.copy_file(local_filename, remote_filename)
        self.assertTrue(os.path.isfile(remote_filename),
                        msg="SFTP copy failed")
        copied_file = open(remote_filename, 'r')
        copied_file_data = copied_file.readlines()[0].strip()
        copied_file.close()
        self.assertEqual(test_file_data, copied_file_data,
                         msg="Data in destination file %s does \
not match source %s" % (copied_file_data, test_file_data))
        os.unlink(local_filename)
        os.unlink(remote_filename)
        client.mkdir(client._make_sftp(), remote_dir)
        self.assertTrue(os.path.isdir(remote_dir))
        os.rmdir(remote_dir)
        del client
        server.join()

if __name__ == '__main__':
    unittest.main()
