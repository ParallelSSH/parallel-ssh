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

from datetime import datetime
from socket import timeout as socket_timeout
from sys import version_info
from collections import deque

from gevent import sleep, spawn, Timeout as GTimeout, socket, joinall
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
        cls.port = 2225
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.user = pwd.getpwuid(os.geteuid()).pw_name
        cls.proxy_host = '127.0.0.9'
        cls.proxy_port = cls.port + 1
        cls.server = OpenSSHServer(listen_ip=cls.proxy_host, port=cls.proxy_port)
        cls.server.start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_tunnel_server(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()
        try:
            client = SSHClient(
                remote_host, port=self.port, pkey=self.user_key,
                num_retries=1,
                proxy_host=self.proxy_host,
                proxy_pkey=self.user_key,
                proxy_port=self.proxy_port,
            )
            output = client.run_command(self.cmd)
            _stdout = list(output.stdout)
            self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(remote_host, client.host)
            self.assertEqual(self.port, client.port)
        finally:
            remote_server.stop()

    def test_tunnel_server_same_port(self):
        remote_host = '127.0.0.7'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.proxy_port)
        remote_server.start_server()
        try:
            client = SSHClient(
                remote_host, port=self.proxy_port, pkey=self.user_key,
                num_retries=1,
                proxy_host=self.proxy_host,
            )
            output = client.run_command(self.cmd)
            _stdout = list(output.stdout)
            self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(remote_host, client.host)
            self.assertEqual(self.proxy_port, client.port)
        finally:
            remote_server.stop()

    def test_tunnel_parallel_client(self):
        hosts = ['127.0.0.1%s' % (d,) for d in range(10)]
        servers = [OpenSSHServer(listen_ip=_host, port=self.port) for _host in hosts]
        for server in servers:
            server.start_server()
        try:
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       )
            start = datetime.now()
            output = client.run_command(self.cmd)
            end = datetime.now()
            dt = end - start
            self.assertTrue(dt.total_seconds() < 2)
            client.join(output)
            self.assertEqual(len(hosts), len(output))
            for i, host_out in enumerate(output):
                _stdout = list(host_out.stdout)
                self.assertListEqual(_stdout, [self.resp])
                self.assertEqual(hosts[i], host_out.host)
        finally:
            for server in servers:
                server.stop()

    def test_tunnel_parallel_client_part_failure(self):
        hosts = ['127.0.0.11', '127.0.0.12', '127.0.0.13', '127.0.0.14']
        servers = [OpenSSHServer(listen_ip=_host, port=self.port) for _host in hosts]
        servers[0].start_server()
        servers[1].start_server()
        try:
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       )
            output = client.run_command(self.cmd, stop_on_errors=False)
            client.join(output)
            self.assertEqual(len(hosts), len(output))
            self.assertTrue(output[2].exception is not None)
            self.assertTrue(output[3].exception is not None)
            self.assertListEqual(list(output[0].stdout), [self.resp])
            self.assertListEqual(list(output[1].stdout), [self.resp])
        finally:
            for server in servers:
                server.stop()

    def test_tunnel_parallel_client_running_fail(self):
        hosts = ['127.0.0.11', '127.0.0.12', '127.0.0.13', '127.0.0.14']
        servers = [OpenSSHServer(listen_ip=_host, port=self.port) for _host in hosts]
        for server in servers:
            server.start_server()
        try:
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       timeout=1,
                                       )
            output = client.run_command(self.cmd)
            client.join(output)
            for server in (servers[2], servers[3]):
                server.stop()
                server.server_proc.communicate()
            client._host_clients[(2, hosts[2])].disconnect()
            client._host_clients[(3, hosts[3])].disconnect()
            output = client.run_command(self.cmd, stop_on_errors=False)
            client.join(output)
            self.assertEqual(len(hosts), len(output))
            self.assertTrue(output[2].exception is not None)
            self.assertTrue(output[3].exception is not None)
            self.assertListEqual(list(output[0].stdout), [self.resp])
            self.assertListEqual(list(output[1].stdout), [self.resp])
        finally:
            for server in servers:
                server.stop()
