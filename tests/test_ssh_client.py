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
        client.copy_file("fake file", "fake file")

class ParallelSSHClientTest(unittest.TestCase):

    def test_parallel_ssh_client(self):
        client = ParallelSSHClient(['testy'])
        cmds = client.exec_command('ls -ltrh')
        try:
            print [client.get_stdout(cmd) for cmd in cmds]
        except UnknownHostException, e:
            print e
            return
        cmds = client.copy_file('fake file', 'fake file')
        client.pool.join()

if __name__ == '__main__':
    unittest.main()
