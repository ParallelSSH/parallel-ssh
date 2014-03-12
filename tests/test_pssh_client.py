#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
import gevent
from pssh import ParallelSSHClient, UnknownHostException, \
    AuthenticationException, ConnectionErrorException, _setup_logger
from fake_server.fake_server import listen, logger as server_logger
import random
import logging

_setup_logger(server_logger)

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'

    def test_pssh_client_exec_command(self):
        listen_port = random.randint(1026, 65534)
        server = gevent.spawn(listen, { self.fake_cmd : self.fake_resp }, listen_port = listen_port)
        server.join(5)
        client = ParallelSSHClient(['localhost'], port=listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'localhost' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        server.kill()
        del client

    def test_pssh_client_auth_failure(self):
        listen_port = random.randint(2048, 65534)
        server = gevent.spawn(listen, { self.fake_cmd : self.fake_resp },
                              listen_port=listen_port, fail_auth=True, )# link_callback=)
        server.join(5)
        client = ParallelSSHClient(['localhost'], port=listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        # Handle exception 
        try:
            cmd.get()
            raise Exception("Expected AuthenticationException, got none")
        except AuthenticationException:
            pass
        server.kill()
        del client
        
