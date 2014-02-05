#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
from pssh import SSHClient, ParallelSSHClient, UnknownHostException
from paramiko import AuthenticationException

class SSHClientTest(unittest.TestCase):

    def test_ssh_client(self):
        try:
            client = SSHClient('testy')
        except UnknownHostException, e:
            print e
            return
        stdin, stdout, stderr = client.exec_command('ls -ltrh')
        for line in stdout:
            print line.strip()

if __name__ == '__main__':
    unittest.main()
