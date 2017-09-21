import unittest
import os
import logging
import time

from .base_ssh2_test import SSH2TestCase
from .embedded_server.openssh import OpenSSHServer
from pssh.ssh2_client import SSHClient, logger as ssh_logger


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class SSH2ClientTest(SSH2TestCase):

    def test_execute(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            self.cmd)
        output = list(stdout)
        stderr = list(stderr)
        expected = [self.resp]
        exit_code = channel.get_exit_status()
        self.assertEqual(exit_code, 0)
        self.assertEqual(expected, output)

    def test_stderr(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'echo "me" >&2')
        self.client.wait_finished(channel)
        output = list(stdout)
        stderr = list(stderr)
        expected = ['me']
        self.assertListEqual(expected, stderr)
        self.assertTrue(len(output) == 0)

    def test_long_running_cmd(self):
        channel, host, stdout, stderr, stdin = self.client.run_command(
            'sleep 2; exit 2')
        self.client.wait_finished(channel)
        exit_code = channel.get_exit_status()
        self.assertEqual(exit_code, 2)
