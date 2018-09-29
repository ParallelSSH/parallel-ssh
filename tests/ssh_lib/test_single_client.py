# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2018 Panos Kittenis
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import unittest
import os
import logging
import time
import subprocess

from gevent import socket, sleep, spawn

from .base_ssh_test import SSHTestCase
from ..embedded_server.openssh import OpenSSHServer
from pssh.clients.ssh_lib.single import SSHClient, logger as ssh_logger
from ssh.session import Session
# from ssh.exceptions import SocketDisconnectError
from pssh.exceptions import AuthenticationException, ConnectionErrorException, \
    SessionError, SFTPIOError, SFTPError, SCPError, PKeyFileError, Timeout


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class SSHClientTest(SSHTestCase):

    def test_context_manager(self):
        with SSHClient(self.host, port=self.port,
                       pkey=self.user_key,
                       num_retries=1) as client:
            self.assertIsInstance(client, SSHClient)

    # def test_auth(self):
    #     client = SSHClient(self.host, port=self.port,
    #                        pkey=PKEY_FILENAME,
    #                        num_retries=1)

    # def test_execute(self):
    #     channel, host, stdout, stderr, stdin = self.client.run_command(
    #         self.cmd)
    #     output = list(stdout)
    #     stderr = list(stderr)
    #     expected = [self.resp]
    #     exit_code = channel.get_exit_status()
    #     self.assertEqual(exit_code, 0)
    #     self.assertEqual(expected, output)
