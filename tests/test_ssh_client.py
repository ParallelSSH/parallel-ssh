#!/usr/bin/env python2.7

"""Unittests for verrot webapp"""

import unittest
from pssh import SSHClient, ParallelSSHClient, UnknownHostException
from paramiko import AuthenticationException

class SSHClientTest(unittest.TestCase):

    def test_ssh_client(self):
        try:
            client = SSHClient('testy')
        except UnknownHostException as e:
            print e
            return
        stdin, stdout, stderr = client.exec_command('ls -ltrh')
        for line in stdout:
            print line.strip()

if __name__ == '__main__':
    unittest.main()
