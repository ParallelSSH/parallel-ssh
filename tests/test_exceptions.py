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
