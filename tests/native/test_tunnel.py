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
import gc

from datetime import datetime
from socket import timeout as socket_timeout
from sys import version_info
from collections import deque
from gevent import sleep, spawn, Timeout as GTimeout

from pssh.config import HostConfig
from pssh.clients.native import SSHClient, ParallelSSHClient
from pssh.clients.native.tunnel import LocalForwarder, TunnelServer, FORWARDER
from pssh.exceptions import UnknownHostException, \
    AuthenticationException, ConnectionErrorException, SessionError, \
    HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \
    ProxyError
from ssh2.exceptions import ChannelFailure, SocketSendError, SocketRecvError

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

    def test_forwarder(self):
        forwarder = LocalForwarder()
        forwarder.daemon = True
        forwarder.start()
        forwarder.started.wait()
        client = SSHClient(
            self.proxy_host, port=self.proxy_port, pkey=self.user_key)
        forwarder.enqueue(client, self.proxy_host, self.port)
        forwarder.out_q.get()
        self.assertTrue(len(forwarder._servers) > 0)
        forwarder.shutdown()

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
    
    # The purpose of this test is to exercise 
    # https://github.com/ParallelSSH/parallel-ssh/issues/304 
    def test_tunnel_server_reconn(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()

        reconn_n = 20       # Number of reconnect attempts
        reconn_delay = 1    # Number of seconds to delay betwen reconnects
        try:
            for _ in range(reconn_n):
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
                client.disconnect()
                FORWARDER._cleanup_servers()
                time.sleep(reconn_delay)
                gc.collect()
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
                retry_delay=.1,
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
        hosts_5 = [hosts[0], hosts[1], hosts[2], hosts[3], hosts[4]]
        try:
            client = ParallelSSHClient(hosts_5, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       )
            start = datetime.now()
            output = client.run_command(self.cmd)
            end = datetime.now()
            dt_5 = end - start
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       )
            start = datetime.now()
            output = client.run_command(self.cmd)
            end = datetime.now()
            dt_10 = end - start
            dt = dt_10.total_seconds() / dt_5.total_seconds()
            # self.assertTrue(dt < 2)
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
        hosts = ['127.0.0.11', '127.0.0.12', '127.0.0.13']
        servers = [OpenSSHServer(listen_ip=_host, port=self.port) for _host in hosts]
        servers[0].start_server()
        try:
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       retry_delay=.1,
                                       )
            output = client.run_command(self.cmd, stop_on_errors=False)
            client.join(output)
            self.assertEqual(len(hosts), len(output))
            self.assertTrue(output[1].exception is not None)
            self.assertTrue(output[2].exception is not None)
            self.assertListEqual(list(output[0].stdout), [self.resp])
        finally:
            for server in servers:
                server.stop()

    def test_tunnel_parallel_client_running_fail(self):
        hosts = ['127.0.0.11', '127.0.0.12', '127.0.0.13']
        servers = [OpenSSHServer(listen_ip=_host, port=self.port) for _host in hosts]
        for server in servers:
            server.start_server()
        try:
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       retry_delay=.1,
                                       )
            output = client.run_command(self.cmd)
            client.join(output)
            for server in (servers[1], servers[2]):
                server.stop()
                server.server_proc.communicate()
            client._host_clients[(1, hosts[1])].disconnect()
            client._host_clients[(2, hosts[2])].disconnect()
            output = client.run_command(self.cmd, stop_on_errors=False)
            client.join(output)
            self.assertEqual(len(hosts), len(output))
            self.assertTrue(output[1].exception is not None)
            self.assertTrue(output[2].exception is not None)
            self.assertListEqual(list(output[0].stdout), [self.resp])
        finally:
            for server in servers:
                server.stop()

    def test_tunnel_host_config(self):
        hosts = ['127.0.0.11', '127.0.0.12']
        servers = [OpenSSHServer(listen_ip=_host, port=self.port) for _host in hosts]
        for server in servers:
            server.start_server()
        host_config = [
            HostConfig(proxy_host=self.proxy_host,
                       proxy_port=self.proxy_port,
                       proxy_pkey=self.user_key),
            HostConfig(proxy_host='127.0.0.155',
                       proxy_port=123),
            ]
        client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                   host_config=host_config, num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
        self.assertIsInstance(output[1].exception, ProxyError)
        stdout = list(output[0].stdout)
        self.assertListEqual(stdout, [self.resp])

    def test_proxy_error(self):
        client = ParallelSSHClient([self.proxy_host], self.port, pkey=self.user_key,
                                   proxy_host='127.0.0.155',
                                   proxy_port=123,
                                   num_retries=1)
        output = client.run_command(self.cmd, stop_on_errors=False)
        client.join(output)
        self.assertIsInstance(output[0].exception, ProxyError)

    def test_proxy_bad_target(self):
        self.assertRaises(
            SocketRecvError, SSHClient,
            '127.0.0.155', port=self.proxy_port, pkey=self.user_key,
            proxy_host=self.proxy_host, proxy_port=self.proxy_port,
            num_retries=1,
        )

    def test_forwarder_exit(self):
        def _start_server():
            raise Exception

        forwarder = LocalForwarder()
        forwarder.daemon = True
        forwarder.start()
        forwarder.started.wait()
        client = SSHClient(
            self.proxy_host, port=self.proxy_port, pkey=self.user_key)
        forwarder.enqueue(client, self.proxy_host, self.port)
        forwarder.out_q.get()
        self.assertTrue(len(forwarder._servers) > 0)
        client.sock.close()
        client.disconnect()
        forwarder._cleanup_servers()
        self.assertEqual(len(forwarder._servers), 0)
        forwarder._start_server = _start_server
        forwarder.enqueue(client, self.proxy_host, self.port)
        sleep(.1)

    def test_socket_channel_error(self):
        class SocketError(Exception):
            pass
        class ChannelFailure(object):
            def read(self):
                raise SocketRecvError
            def write(self, data):
                raise SocketSendError
            def eof(self):
                return False
            def close(self):
                return
        class Channel(object):
            def __init__(self):
                self._eof = False
            def read(self):
                return 5, b"asdfa"
            def write(self, data):
                return 0, len(data)
            def eof(self):
                return self._eof
            def close(self):
                return
        class Socket(object):
            def recv(self, num):
                return b"asdfaf"
            def close(self):
                return
        class SocketFailure(object):
            def sendall(self, data):
                raise SocketError
            def recv(self, num):
                raise SocketError
            def close(self):
                return
        class SocketEmpty(object):
            def recv(self, num):
                return b""
            def close(self):
                return
        client = SSHClient(
            self.proxy_host, port=self.proxy_port, pkey=self.user_key)
        server = TunnelServer(client, self.proxy_host, self.port)
        let = spawn(server._read_forward_sock, SocketEmpty(), Channel())
        let.start()
        sleep(.01)
        self.assertRaises(SocketSendError, server._read_forward_sock, Socket(), ChannelFailure())
        self.assertRaises(SocketError, server._read_forward_sock, SocketFailure(), Channel())
        self.assertRaises(SocketError, server._read_channel, SocketFailure(), Channel())
        self.assertRaises(SocketRecvError, server._read_channel, Socket(), ChannelFailure())
        channel = Channel()
        _socket = Socket()
        source_let = spawn(server._read_forward_sock, _socket, channel)
        dest_let = spawn(server._read_channel, _socket, channel)
        channel._eof = True
        self.assertIsNone(server._wait_send_receive_lets(source_let, dest_let, channel, _socket))
        let.kill()

    def test_server_start(self):
        _port = 1234
        class Server(object):
            def __init__(self):
                self.started = False
                self.listen_port = _port
        server = Server()
        forwarder = LocalForwarder()
        let = spawn(forwarder._get_server_listen_port, None, server)
        let.start()
        sleep(.01)
        server.started = True
        sleep(.01)
        with GTimeout(seconds=1):
            port = forwarder.out_q.get()
        self.assertEqual(port, _port)
