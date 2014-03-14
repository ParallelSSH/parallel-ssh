#!/usr/bin/env python

"""Unittests for parallel-ssh"""

import unittest
from pssh import ParallelSSHClient, UnknownHostException, \
    AuthenticationException, ConnectionErrorException, _setup_logger
from fake_server.fake_server import listen, make_socket, logger as server_logger
import random
import logging
import gevent
import threading

_setup_logger(server_logger)

class ParallelSSHClientTest(unittest.TestCase):

    def setUp(self):
        self.fake_cmd = 'fake cmd'
        self.fake_resp = 'fake response'
        self.listener = make_socket('127.0.0.1')
        self.listen_port = self.listener.getsockname()[1]

    def cleanUp(self):
        del self.listener

    def _run_client_exec_command(self):
        client = ParallelSSHClient(['localhost'], port=self.listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        output = client.get_stdout(cmd)
        expected = {'localhost' : {'exit_code' : 0}}
        self.assertEqual(expected, output,
                         msg = "Got unexpected command output - %s" % (output,))
        gevent.sleep(0)
        del client

    def _run_client_fail_auth(self):
        client = ParallelSSHClient(['localhost'], port=self.listen_port)
        cmd = client.exec_command(self.fake_cmd)[0]
        # Handle exception
        try:
            cmd.get()
            raise Exception("Expected AuthenticationException, got none")
        except AuthenticationException:
            pass
        del client

    def test_pssh_client_exec_command(self):
        server = listen({ self.fake_cmd : self.fake_resp }, self.listener)
        client = threading.Thread(target=self._run_client_exec_command)
        client.start()
        client.join()
        server.join()

    def test_pssh_client_auth_failure(self):
        server = listen({ self.fake_cmd : self.fake_resp },
                        self.listener, fail_auth=True)
        client = threading.Thread(target=self._run_client_fail_auth)
        client.start()
        client.join()
        server.join()
