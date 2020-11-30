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

import unittest
import pwd
import os
import shutil
import sys
import string
import random
import time

from socket import timeout as socket_timeout
from sys import version_info
from collections import deque

from gevent import sleep, spawn, Timeout as GTimeout, socket, joinall
from pssh.clients.native.tunnel_server import TunnelServer, ThreadedServer
from pssh.clients.native import SSHClient, ParallelSSHClient
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError
from ssh2.exceptions import ChannelFailure, SocketSendError
from ssh2.session import LIBSSH2_TRACE_SOCKET, LIBSSH2_TRACE_ERROR, \
    LIBSSH2_TRACE_CONN

from .base_ssh2_case import PKEY_FILENAME, PUB_FILE
from ..embedded_server.openssh import OpenSSHServer


class TunnelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(PKEY_FILENAME, _mask)
        cls.host = '127.0.0.1'
        cls.port = 2225
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.user = pwd.getpwuid(os.geteuid()).pw_name
        cls.proxy_host = '127.0.0.9'
        cls.server = OpenSSHServer(listen_ip=cls.proxy_host, port=cls.port)
        cls.server.start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_tunnel_server(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()
        proxy_client = SSHClient(self.proxy_host, port=self.port, pkey=self.user_key,
                                 num_retries=1,
                                 proxy_pkey=self.user_key,
                                 _auth_thread_pool=False)
        tunnel_server = ThreadedServer()
        tunnel_server.daemon = True
        tunnel_server.start()
        tunnel_server.started.wait()
        tunnel_server.in_q.put(proxy_client)
        proxy_local_port = tunnel_server.out_q.get()
        proxy_local_addr = '127.0.0.1'
        try:
            client = SSHClient(
                proxy_local_addr, port=proxy_local_port, pkey=self.user_key,
                num_retries=1,
                _auth_thread_pool=True)
            output = client.run_command(self.cmd)
            _stdout = list(output.stdout)
            self.assertListEqual(_stdout, [self.resp])
        finally:
            # tunnel_server.server.stop()
            remote_server.stop()
