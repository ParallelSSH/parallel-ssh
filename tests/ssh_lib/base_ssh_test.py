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
import pwd
import os
import logging
import socket
from sys import version_info

from ..embedded_server.openssh import OpenSSHServer
from pssh.clients.ssh_lib.single import SSHClient, logger as ssh_logger


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()

PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), '..', 'client_pkey'])
PUB_FILE = "%s.pub" % (PKEY_FILENAME,)


class SSHTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.server = OpenSSHServer()
        cls.server.start_server()
        cls.host = '127.0.0.1'
        cls.port = 2222
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.user = pwd.getpwuid(os.geteuid()).pw_name
        cls.client = SSHClient(cls.host, port=cls.port,
                               pkey=PKEY_FILENAME,
                               num_retries=1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        del cls.server
