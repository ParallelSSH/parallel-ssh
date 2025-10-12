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

import logging
import os
import subprocess
import unittest
from getpass import getuser
from sys import version_info

from pssh.clients.ssh.single import SSHClient
from ..embedded_server.openssh import OpenSSHServer


def setup_root_logger():
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)


setup_root_logger()


PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), '..', 'client_pkey'])
PUB_FILE = "%s.pub" % (PKEY_FILENAME,)
USER_CERT_PRIV_KEY_NAME = 'int_test_cert_key'
USER_CERT_PRIV_KEY = os.path.sep.join([os.path.dirname(__file__), '..', USER_CERT_PRIV_KEY_NAME])
USER_CERT_PUB_KEY = os.path.sep.join([
    os.path.dirname(__file__),
    '..',
    "%s.pub" % (USER_CERT_PRIV_KEY_NAME,),
])
USER_CERT_FILE = os.path.sep.join([
    os.path.dirname(__file__),
    '..',
    "%s-cert.pub" % (USER_CERT_PRIV_KEY_NAME,),
])
CA_USER_KEY = os.path.sep.join([os.path.dirname(__file__), '..', 'embedded_server', 'ca_user_key'])
USER = getuser()


def sign_cert():
    cmd = [
        'ssh-keygen', '-s', CA_USER_KEY, '-n', USER, '-I', 'tests', USER_CERT_PUB_KEY,
    ]
    subprocess.check_call(cmd)


class SSHTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        for _file in [PKEY_FILENAME, USER_CERT_PRIV_KEY, CA_USER_KEY]:
            os.chmod(_file, _mask)
        sign_cert()
        # import ipdb; ipdb.set_trace()
        cls.host = '127.0.0.1'
        cls.port = 2322
        cls.server = OpenSSHServer(listen_ip=cls.host, port=cls.port)
        cls.server.start_server()
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.cert_pkey = USER_CERT_PRIV_KEY
        cls.cert_file = USER_CERT_FILE
        cls.user = USER
        cls.client = SSHClient(cls.host, port=cls.port,
                               pkey=PKEY_FILENAME,
                               num_retries=1,
                               identity_auth=False,
                               retry_delay=.1,
                               )

    @classmethod
    def tearDownClass(cls):
        del cls.client
        cls.server.stop()
        del cls.server
