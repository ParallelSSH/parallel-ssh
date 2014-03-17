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
        # self.listener = make_socket('127.0.0.1')
        # self.listen_port = self.listener.getsockname()[1]

    # def cleanUp(self):
    #     del self.listener

    def test_pssh_client_exec_command(self):
        sock = make_socket('127.0.0.1')
        listen_port = sock.getsockname()[1]
        server = start_server({ self.fake_cmd : self.fake_resp }, sock)
        gevent.sleep(1)
        client = ParallelSSHClient(['localhost'], port=listen_port)
        gevent.sleep(2)
        cmd = client.exec_command(self.fake_cmd)[0]
        gevent.sleep(2)
        output = client.get_stdout(cmd)
        expected = {'localhost' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        del client
        server.join()

    def test_pssh_client_auth_failure(self):
        sock = make_socket('127.0.0.1')
        listen_port = sock.getsockname()[1]
        server = start_server({ self.fake_cmd : self.fake_resp },
                              sock, fail_auth=True)
        gevent.sleep(1)
        client = ParallelSSHClient(['localhost'], port=listen_port)
        gevent.sleep(2)
        cmd = client.exec_command(self.fake_cmd)[0]
        gevent.sleep(2)
        # Handle exception
        try:
            cmd.get()
            raise Exception("Expected AuthenticationException, got none")
        except AuthenticationException:
            pass
        del client
        server.join()
