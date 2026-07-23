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

from pssh.exceptions import AuthenticationError, AuthenticationException, UnknownHostError, \
    UnknownHostException, ConnectionError, ConnectionErrorException, SSHError, SSHException, \
    HostArgumentError, HostArgumentException
from pssh.exceptions import SCPError, Timeout


class ParallelSSHUtilsTest(unittest.TestCase):

    def test_exceptions(self):
        try:
            raise AuthenticationError
        except AuthenticationException:
            pass
        try:
            raise UnknownHostException
        except UnknownHostError:
            pass
        try:
            raise ConnectionErrorException
        except ConnectionError:
            pass
        try:
            raise SSHException
        except SSHError:
            pass
        try:
            raise HostArgumentException
        except HostArgumentError:
            pass

    def test_errors(self):
        try:
            raise AuthenticationException
        except AuthenticationError:
            pass
        try:
            raise UnknownHostError
        except UnknownHostException:
            pass
        try:
            raise ConnectionError
        except ConnectionErrorException:
            pass
        try:
            raise SSHError
        except SSHException:
            pass
        try:
            raise HostArgumentError
        except HostArgumentException:
            pass

    def test_formatted_error_string(self):
        message = "Authentication error while connecting to %s:%s - %s - retries %s/%s"
        cause = AuthenticationError("No authentication methods succeeded")
        error = AuthenticationError(
            message, "host.example.com", 22, cause, 3, 3)

        self.assertEqual(
            str(error),
            "Authentication error while connecting to host.example.com:22 - "
            "No authentication methods succeeded - retries 3/3")
        self.assertEqual(
            error.args,
            (message, "host.example.com", 22, cause, 3, 3))

    def test_invalid_formatted_error_falls_back_to_default(self):
        error = Timeout("Timeout after %s seconds: %s", 10)

        self.assertEqual(str(error), str(Exception(*error.args)))

    def test_single_argument_error_string_is_unchanged(self):
        self.assertEqual(str(SCPError("copy failed")), "copy failed")
