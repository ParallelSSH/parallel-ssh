# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2020 Panos Kittenis
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


"""Unittests for :mod:`pssh.output.HostOutput` class"""


import unittest

from pssh.output import HostOutput


class TestHostOutput(unittest.TestCase):

    def setUp(self):
        self.output = HostOutput(None, None, None, None, None, None, True)

    def test_print(self):
        self.assertTrue(str(self.output))

    def test_bad_exit_status(self):
        self.assertIsNone(self.output.exit_code)

    def test_excepting_client_exit_code(self):
        class ExcSSHClient(object):
            def get_exit_status(self, channel):
                raise Exception
        exc_client = ExcSSHClient()
        host_out = HostOutput(
            'host', None, None, None, None, None, exc_client, None)
        exit_code = host_out.exit_code
        self.assertEqual(exit_code, None)
