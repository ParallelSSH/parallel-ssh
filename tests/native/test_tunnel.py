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
from pssh.clients.native.tunnel import Tunnel
from pssh.clients.native import SSHClient, ParallelSSHClient
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError
from ssh2.exceptions import ChannelFailure, SocketSendError

from .base_ssh2_case import PKEY_FILENAME, PUB_FILE
from ..embedded_server.openssh import ThreadedOpenSSHServer, OpenSSHServer


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

    def test_tunnel_retries(self):
        local_port = 3050
        fw_host, fw_port = '127.0.0.1', 2100
        in_q = deque()
        out_q = deque()
        t = Tunnel(self.proxy_host, in_q, out_q, port=self.port,
                   pkey=self.user_key, num_retries=2)
        t.daemon = True
        t.start()
        in_q.append((fw_host, fw_port))
        while not t.tunnel_open.is_set():
            sleep(.1)
        _port = out_q.pop()
        try:
            fw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            fw_socket.connect(('127.0.0.1', _port))
            sleep(1)
            self.assertIsInstance(t.exception, ChannelFailure)
        finally:
            fw_socket.close()

    def test_tunnel_channel_failure(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()
        in_q, out_q = deque(), deque()
        try:
            tunnel = Tunnel(self.proxy_host, in_q, out_q, port=self.port,
                            pkey=self.user_key, num_retries=1)
            tunnel.daemon = True
            tunnel.start()
            in_q.append((remote_host, self.port))
            while not tunnel.tunnel_open.is_set():
                sleep(.1)
                if not tunnel.is_alive():
                    raise ProxyError
            self.assertTrue(tunnel.tunnel_open.is_set())
            self.assertIsNotNone(tunnel.client)
            while True:
                try:
                    _port = out_q.pop()
                except IndexError:
                    sleep(.5)
                else:
                    break
            proxy_client = SSHClient(
                '127.0.0.1', pkey=self.user_key, port=_port,
                num_retries=1, _auth_thread_pool=False)
            cmd = spawn(proxy_client.execute, 'echo me')
            proxy_client.disconnect()
            joinall([cmd])
            self.assertEqual(proxy_client.sock, None)
        finally:
            remote_server.stop()

    def test_tunnel_server_failure(self):
        proxy_host = '127.0.0.9'
        remote_host = '127.0.0.8'
        server = OpenSSHServer(listen_ip=proxy_host, port=self.port)
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        for _server in (server, remote_server):
            _server.start_server()
        in_q, out_q = deque(), deque()
        try:
            tunnel = Tunnel(proxy_host, in_q, out_q, port=self.port,
                            pkey=self.user_key, num_retries=1)
            tunnel.daemon = True
            tunnel.start()
            in_q.append((remote_host, self.port))
            while not tunnel.tunnel_open.is_set():
                sleep(.1)
                if not tunnel.is_alive():
                    raise ProxyError
            self.assertTrue(tunnel.tunnel_open.is_set())
            self.assertIsNotNone(tunnel.client)
            while True:
                try:
                    _port = out_q.pop()
                except IndexError:
                    sleep(.5)
                else:
                    break
            proxy_client = spawn(SSHClient,
                                 '127.0.0.1', pkey=self.user_key, port=_port,
                                 num_retries=1, _auth_thread_pool=False)
            stop_cmd = spawn(remote_server.stop)
            joinall([proxy_client, stop_cmd])
        finally:
            for _server in (server, remote_server):
                _server.stop()

    def test_tunnel(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()
        try:
            client = ParallelSSHClient(
                [remote_host], port=self.port, pkey=self.user_key,
                proxy_host=self.proxy_host, proxy_port=self.port, num_retries=1,
                proxy_pkey=self.user_key)
            output = client.run_command(self.cmd)
            client.join(output)
            for host_out in output:
                _stdout = list(host_out.stdout)
                self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(remote_host, output[0].host)
            del client
        finally:
            remote_server.stop()

    def test_tunnel_init_failure(self):
        proxy_host = '127.0.0.20'
        client = ParallelSSHClient(
            [self.host], port=self.port, pkey=self.user_key,
            proxy_host=proxy_host, proxy_port=self.port, num_retries=1,
            proxy_pkey=self.user_key)
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
        exc = output[0].exception
        self.assertIsInstance(exc, ProxyError)
        self.assertIsInstance(exc.args[1], ConnectionErrorException)

    def test_single_tunnel_multi_hosts(self):
        remote_host = '127.0.0.8'
        remote_server = ThreadedOpenSSHServer(
            listen_ip=remote_host, port=self.port)
        remote_server.start()
        remote_server.wait_for_port()
        hosts = [remote_host, remote_host, remote_host]
        try:
            client = ParallelSSHClient(
                hosts, port=self.port, pkey=self.user_key,
                proxy_host=self.proxy_host, proxy_port=self.port, num_retries=1,
                proxy_pkey=self.user_key)
            output = client.run_command(self.cmd, stop_on_errors=False)
            client.join(output)
            for host_out in output:
                _stdout = list(host_out.stdout)
                self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(len(hosts), len(output))
            del client
        finally:
            remote_server.stop()
            remote_server.join()

    def test_single_tunnel_multi_hosts_timeout(self):
        remote_host = '127.0.0.8'
        remote_server = ThreadedOpenSSHServer(
            listen_ip=remote_host, port=self.port)
        remote_server.start()
        remote_server.wait_for_port()
        hosts = [remote_host, remote_host, remote_host]
        try:
            client = ParallelSSHClient(
                hosts, port=self.port, pkey=self.user_key,
                proxy_host=self.proxy_host, proxy_port=self.port, num_retries=1,
                proxy_pkey=self.user_key,
                timeout=.001)
            output = client.run_command(self.cmd, stop_on_errors=False)
            client.join(output)
            for host_out in output:
                self.assertIsInstance(host_out.exception, Timeout)
        finally:
            remote_server.stop()
            remote_server.join()
