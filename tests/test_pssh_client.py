#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
from pssh import ParallelSSHClient, UnknownHostException, \
    AuthenticationException, ConnectionErrorException, _setup_logger
from fake_server.fake_server import start_server, make_socket, logger as server_logger
import random
import logging
import gevent
import threading

_setup_logger(server_logger)

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'

    def test_pssh_client_exec_command(self):
        sock = make_socket('127.0.0.1')
        listen_port = sock.getsockname()[1]
        server = start_server({ self.fake_cmd : self.fake_resp }, sock)
        client = ParallelSSHClient(['127.0.0.1'], port=listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'127.0.0.1' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        del client
        server.join()

    def test_pssh_client_auth_failure(self):
        sock = make_socket('127.0.0.1')
        listen_port = sock.getsockname()[1]
        server = start_server({ self.fake_cmd : self.fake_resp },
                              sock, fail_auth=True)
        client = ParallelSSHClient(['127.0.0.1'], port=listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        # Handle exception
        try:
            cmd.get()
            raise Exception("Expected AuthenticationException, got none")
        except AuthenticationException:
            pass
        del client
        server.join()
