#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import unittest
from subprocess import TimeoutExpired
from unittest.mock import patch

from .embedded_server import openssh
from .embedded_server.openssh import OpenSSHServer, OpenSSHServerError


class ExitedProcess(object):
    """sshd that has already exited, e.g. after failing to bind."""
    returncode = 255

    def __init__(self):
        self.waits = 0

    def wait(self, timeout=None):
        # Waiting on an exited process returns at once, so a start-up loop
        # that keeps waiting would never end - fail instead of hanging.
        self.waits += 1
        if self.waits > 10:
            raise AssertionError("Exited sshd process waited on repeatedly")
        return self.returncode


class RunningProcess(object):
    returncode = None

    def wait(self, timeout=None):
        raise TimeoutExpired('sshd', timeout)


class OpenSSHServerTest(unittest.TestCase):

    def setUp(self):
        self.server = OpenSSHServer(listen_ip='127.0.0.50', port=2290)

    def tearDown(self):
        self.server.server_proc = None
        self.server.stop()

    @patch.object(openssh, 'Popen')
    def test_start_server_raises_when_sshd_exits(self, popen):
        popen.return_value = ExitedProcess()
        self.assertRaises(OpenSSHServerError, self.server.start_server)
        self.assertEqual(popen.return_value.waits, 1)

    @patch.object(openssh, 'Popen')
    def test_start_server_returns_while_sshd_runs(self, popen):
        popen.return_value = RunningProcess()
        self.server.start_server()
        self.assertIs(self.server.server_proc, popen.return_value)
