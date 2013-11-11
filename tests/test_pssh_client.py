#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
import gevent
from gevent import monkey
monkey.patch_all()
from pssh import ParallelSSHClient, UnknownHostException
from paramiko import AuthenticationException
from fake_server.fake_server import listen

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'

    def test_pssh_client_exec_command(self):
        server = gevent.spawn(listen, { self.fake_cmd : self.fake_resp })
        client = ParallelSSHClient(['localhost'], port = 2200)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'localhost' : {'exit_code' : 0}}
        self.assertEqual(expected, output, msg = "Got unexpected command output - %s" % (output,))
        server.kill()

    def test_pssh_client_auth_failure(self):
        server = gevent.spawn(listen, { self.fake_cmd : self.fake_resp }, listen_port = 2201, fail_auth = True)
        client = ParallelSSHClient(['localhost'], port = 2201)
        try:
            cmd = client.exec_command(self.fake_cmd)[0]
        except AuthenticationException:
            pass
