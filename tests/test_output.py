#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2015- Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


"""Unittests for :mod:`pssh.output.HostOutput` class"""


import unittest
import logging

from pssh import logger
from pssh.output import HostOutput

logger.setLevel(logging.DEBUG)
logging.basicConfig()


class TestHostOutput(unittest.TestCase):

    def setUp(self):
        self.output = HostOutput(None, None, None, None, None, None, True)

    def test_print(self):
        self.assertTrue(str(self.output))

    def test_update(self):
        host, cmd, chan, stdout, stderr, \
          stdin, exception = 'host', 'cmd', 'chan', 'stdout', \
          'stderr', 'stdin', Exception()
        self.output.update({'host': host,
                            'cmd': cmd,
                            'channel': chan,
                            'stdout': stdout,
                            'stderr': stderr,
                            'stdin': stdin,
                            'exception': exception})
        self.assertEqual(host, self.output.host)
        self.assertEqual(self.output.host, self.output['host'])
        self.assertEqual(cmd, self.output.cmd)
        self.assertEqual(self.output.cmd, self.output['cmd'])
        self.assertEqual(chan, self.output.channel)
        self.assertEqual(self.output.channel, self.output['channel'])
        self.assertEqual(stdout, self.output.stdout)
        self.assertEqual(self.output.stdout, self.output['stdout'])
        self.assertEqual(stderr, self.output.stderr)
        self.assertEqual(self.output.stderr, self.output['stderr'])
        self.assertEqual(stdin, self.output.stdin)
        self.assertEqual(self.output.stdin, self.output['stdin'])
        self.assertEqual(exception, self.output.exception)
        self.assertEqual(self.output.exception, self.output['exception'])

    def test_bad_exit_status(self):
        self.assertEqual(self.output.exit_code, None)

    def test_excepting_client_exit_code(self):
        class ExcSSHClient(object):
            def get_exit_status(self, channel):
                raise Exception
        exc_client = ExcSSHClient()
        host_out = HostOutput(
            'host', None, None, None, None, None, exc_client, None)
        exit_code = host_out.exit_code
        self.assertEqual(exit_code, None)
