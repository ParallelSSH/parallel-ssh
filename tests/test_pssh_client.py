#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
import gevent
from gevent import monkey
monkey.patch_all()
from pssh import ParallelSSHClient, UnknownHostException, ConnectionErrorException
from paramiko import AuthenticationException
from fake_server.fake_server import listen
import random

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'

    def test_pssh_client_exec_command(self):
        listen_port = random.randint(1025, 65534)
        server = gevent.spawn(listen, { self.fake_cmd : self.fake_resp }, listen_port = listen_port)
        client = ParallelSSHClient(['localhost'], port = listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'localhost' : {'exit_code' : 0}}
        self.assertEqual(expected, output, msg = "Got unexpected command output - %s" % (output,))
        server.kill()

    def test_pssh_client_auth_failure(self):
        listen_port = random.randint(1025, 65534)
        server = gevent.spawn(listen, { self.fake_cmd : self.fake_resp }, listen_port = listen_port, fail_auth = True)
        client = ParallelSSHClient(['localhost'], port = listen_port)
        try:
            cmd = client.exec_command(self.fake_cmd)[0]
        except AuthenticationException:
            pass
        server.kill()
