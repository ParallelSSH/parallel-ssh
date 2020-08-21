# This file is part of parallel-ssh.
#
# Copyright (C) 2015-2020 Panos Kittenis
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

from __future__ import print_function

import unittest
import pwd
import os
import shutil
import sys
import string
from socket import timeout as socket_timeout
from sys import version_info
import random
import time
from collections import deque

from gevent import sleep, spawn, Timeout as GTimeout, socket
from pssh.clients.native.tunnel import Tunnel
from pssh.clients.native import SSHClient, ParallelSSHClient
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError
from ssh2.exceptions import ChannelFailure, SocketSendError

from .embedded_server.openssh import ThreadedOpenSSHServer, OpenSSHServer
from .base_ssh2_case import PKEY_FILENAME, PUB_FILE


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
        t = Tunnel(self.proxy_host, deque(), deque(), port=self.port,
                   pkey=self.user_key, num_retries=2)
        t._init_tunnel_client()
        try:
            t._open_channel_retries(fw_host, fw_port, local_port)
        except (ChannelFailure, SocketSendError) as ex:
            pass
        else:
            raise AssertionError(ex)

    def _connect_client(self, _socket):
        while True:
            _socket.read()

    def test_tunnel_channel_eof(self):
        remote_host = '127.0.0.59'
        server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        server.start_server()
        in_q, out_q = deque(), deque()
        try:
            tunnel = Tunnel(self.proxy_host, in_q, out_q, port=self.port,
                            pkey=self.user_key, num_retries=1)
            tunnel._init_tunnel_client()
            channel = tunnel._open_channel_retries(self.proxy_host, self.port, 2150)
            self.assertFalse(channel.eof())
            channel.close()
            listen_socket, listen_port = tunnel._init_tunnel_sock()
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('127.0.0.1', listen_port))
            client = spawn(self._connect_client, client_socket)
            tunnel._read_channel(client_socket, channel)
            tunnel._read_forward_sock(client_socket, channel)
            self.assertTrue(channel.eof())
            client.kill()
        finally:
            server.stop()

    def test_tunnel_sock_failure(self):
        remote_host = '127.0.0.59'
        server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        server.start_server()
        in_q, out_q = deque(), deque()
        try:
            tunnel = Tunnel(self.proxy_host, in_q, out_q, port=self.port,
                            pkey=self.user_key, num_retries=1)
            tunnel._init_tunnel_client()
            channel = tunnel._open_channel_retries(self.proxy_host, self.port, 2150)
            self.assertFalse(channel.eof())
            listen_socket, listen_port = tunnel._init_tunnel_sock()
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('127.0.0.1', listen_port))
            client_socket.send(b'blah\n')
            client_socket.close()
            gl1 = spawn(tunnel._read_channel, client_socket, channel)
            gl2 = spawn(tunnel._read_forward_sock, client_socket, channel)
            sleep(1)
            gl1.kill()
            gl2.kill()
            tunnel._sockets.append(None)
            tunnel.cleanup()
        finally:
            server.stop()

    def test_tunnel_init(self):
        proxy_host = '127.0.0.49'
        server = OpenSSHServer(listen_ip=proxy_host, port=self.port)
        server.start_server()
        in_q, out_q = deque(), deque()
        try:
            tunnel = Tunnel(proxy_host, in_q, out_q, port=self.port,
                            pkey=self.user_key, num_retries=1)
            tunnel._init_tunnel_client()
            consume_let = spawn(tunnel._consume_q)
            in_q.append((self.host, self.port))
            while not tunnel.tunnel_open.is_set():
                sleep(.1)
                if not tunnel.is_alive():
                    raise ProxyError
            self.assertTrue(tunnel.tunnel_open.is_set())
            self.assertIsNotNone(tunnel.client)
            tunnel.cleanup()
            for _sock in tunnel._sockets:
                self.assertTrue(_sock.closed)
        finally:
            server.stop()

    def test_tunnel_channel_exc(self):
        remote_host = '127.0.0.69'
        server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        server.start_server()
        in_q, out_q = deque(), deque()
        try:
            tunnel = Tunnel(remote_host, in_q, out_q, port=self.port,
                            pkey=self.user_key, num_retries=1)
            tunnel._init_tunnel_client()
            tunnel_accept = spawn(tunnel._start_tunnel, '127.0.0.255', self.port)
            while len(out_q) == 0:
                sleep(1)
            listen_port = out_q.pop()
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('127.0.0.1', listen_port))
            client = spawn(self._connect_client, client_socket)
            sleep(1)
            client.kill()
            tunnel_accept.kill()
            for _sock in tunnel._sockets:
                self.assertTrue(_sock.closed)
        finally:
            server.stop()

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
            tunnel.cleanup()
            spawn(proxy_client.execute, 'echo me')
            proxy_client.disconnect()
            self.assertTrue(proxy_client.sock.closed)
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
            tunnel._init_tunnel_client()
            consume_let = spawn(tunnel._consume_q)
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
            proxy_client = spawn(
                SSHClient,
                '127.0.0.1', pkey=self.user_key, port=_port,
                num_retries=1, _auth_thread_pool=False)
            remote_server.stop()
            tunnel.cleanup()
            self.assertRaises(ConnectionErrorException, proxy_client.get)
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
            for host, host_out in output.items():
                _stdout = list(host_out.stdout)
                self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(remote_host, list(output.keys())[0])
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
        exc = output[self.host].exception
        self.assertIsInstance(exc, ProxyError)
        self.assertIsInstance(exc.args[1], ConnectionErrorException)

    def test_tunnel_remote_host_timeout(self):
        remote_host = '127.0.0.18'
        proxy_host = '127.0.0.19'
        server = ThreadedOpenSSHServer(listen_ip=proxy_host, port=self.port)
        remote_server = ThreadedOpenSSHServer(listen_ip=remote_host, port=self.port)
        for _server in (server, remote_server):
            _server.start()
            _server.wait_for_port()
        try:
            client = ParallelSSHClient(
                [remote_host], port=self.port, pkey=self.user_key,
                proxy_host=proxy_host, proxy_port=self.port, num_retries=1,
                proxy_pkey=self.user_key)
            output = client.run_command(self.cmd)
            client.join(output)
            client._tunnel.cleanup()
            for _server in (server, remote_server):
                _server.stop()
                _server.join()
            # Gevent timeout cannot be caught by stop_on_errors
            self.assertRaises(GTimeout, client.run_command, self.cmd,
                              greenlet_timeout=1, stop_on_errors=False)
        finally:
            for _server in (server, remote_server):
                _server.stop()

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
            for host, host_out in output.items():
                _stdout = list(host_out.stdout)
                self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(len(hosts), len(list(output.keys())))
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
            for host, host_out in output.items():
                self.assertIsInstance(output[host].exception, Timeout)
        finally:
            remote_server.stop()
            remote_server.join()
