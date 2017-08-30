import unittest
import pwd
import os
import logging
import socket
from sys import version_info

from .embedded_server.openssh import OpenSSHServer
from ssh2.session import Session
from pssh.ssh2_client import SSHClient, logger as ssh_logger


ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()

PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'client_pkey'])
PUB_FILE = "%s.pub" % (PKEY_FILENAME,)


class SSH2TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.server = OpenSSHServer()
        cls.server.start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        del cls.server

    def setUp(self):
        self.host = '127.0.0.1'
        self.port = 2222
        self.cmd = 'echo me'
        self.resp = u'me'
        self.user_key = PKEY_FILENAME
        self.user_pub_key = PUB_FILE
        self.user = pwd.getpwuid(os.geteuid()).pw_name
        self.client = SSHClient(self.host, port=self.port,
                                pkey=PKEY_FILENAME,
                                num_retries=1)
