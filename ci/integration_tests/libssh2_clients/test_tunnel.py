# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2022 Panos Kittenis and contributors.
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

import gc
import os
import time
import unittest

from unittest.mock import MagicMock
from getpass import getuser
from gevent import sleep, spawn
from ssh2.exceptions import SocketSendError, SocketRecvError
from sys import version_info

from pssh.clients.native import SSHClient, ParallelSSHClient
from pssh.clients.native.tunnel import LocalForwarder, TunnelServer
from pssh.config import HostConfig
from pssh.exceptions import ProxyError
from .base_ssh2_case import PKEY_FILENAME, PUB_FILE
from ..embedded_server.openssh import OpenSSHServer


class TunnelTest(unittest.TestCase):
    server = None

    @classmethod
    def setUpClass(cls):
        _mask = int('0600') if version_info <= (2,) else 0o600
        port = 2225
        os.chmod(PKEY_FILENAME, _mask)
        cls.port = port
        cls.cmd = 'echo me'
        cls.resp = u'me'
        cls.user_key = PKEY_FILENAME
        cls.user_pub_key = PUB_FILE
        cls.user = getuser()
        cls.proxy_host = '127.0.0.9'
        cls.proxy_port = port + 1
        cls.server = OpenSSHServer(listen_ip=cls.proxy_host, port=cls.proxy_port)
        cls.server.start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_forwarder(self):
        forwarder = LocalForwarder()
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

    def test_proxy_pkey_bytes_data(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()
        with open(self.user_key, 'rb') as fh:
            pkey_data = fh.read()
        try:
            client = ParallelSSHClient(
                [remote_host], port=self.port, pkey=pkey_data,
                num_retries=1,
                proxy_host=self.proxy_host,
                proxy_pkey=pkey_data,
                proxy_port=self.proxy_port,
            )
            output = client.run_command(self.cmd)
            _stdout = list(output[0].stdout)
            self.assertListEqual(_stdout, [self.resp])
            self.assertEqual(remote_host, output[0].host)
            self.assertEqual(self.port, client.port)
        finally:
            remote_server.stop()

    # The purpose of this test is to exercise
    # https://github.com/ParallelSSH/parallel-ssh/issues/304
    def test_tunnel_server_reconn(self):
        remote_host = '127.0.0.8'
        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)
        remote_server.start_server()

        reconn_n = 10        # Number of reconnect attempts
        reconn_delay = .1    # Number of seconds to delay between reconnects
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
                client.wait_finished(output)
                self.assertEqual(remote_host, client.host)
                self.assertEqual(self.port, client.port)
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
        hosts = ['127.0.0.1%s' % (d,) for d in range(5)]
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
            client.run_command(self.cmd)
            client = ParallelSSHClient(hosts, port=self.port, pkey=self.user_key,
                                       proxy_host=self.proxy_host,
                                       proxy_pkey=self.user_key,
                                       proxy_port=self.proxy_port,
                                       num_retries=1,
                                       )
            output = client.run_command(self.cmd)
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
            client._host_clients[(1, hosts[1])].sock.close()
            client._host_clients[(2, hosts[2])].sock.close()
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
        self.assertTrue(output[0].exception is None)
        stdout = list(output[0].stdout)
        self.assertListEqual(stdout, [self.resp])

    def test_proxy_error(self):
        client = ParallelSSHClient([self.proxy_host], port=self.port, pkey=self.user_key,
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
        forwarder.start()
        forwarder.started.wait()
        client = SSHClient(
            self.proxy_host, port=self.proxy_port, pkey=self.user_key)
        forwarder.enqueue(client, self.proxy_host, self.port)
        forwarder.out_q.get()
        self.assertTrue(len(forwarder._servers) > 0)
        forwarder.shutdown()
        self.assertEqual(len(forwarder._servers), 0)
        forwarder._start_server = _start_server
        forwarder.enqueue(client, self.proxy_host, self.port)
        sleep(.1)
        self.assertEqual(len(forwarder._servers), 0)

    def test_forwarder_join(self):
        forwarder = LocalForwarder()
        forwarder.start()
        forwarder.started.wait()
        mock_join = MagicMock()
        mock_join.side_effect = RuntimeError
        forwarder.join = mock_join
        # Shutdown should not raise exception
        self.assertIsNone(forwarder.shutdown())

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
            closed = False

            def recv(self, num):
                return b"asdfaf"

            def close(self):
                return

        class SocketFailure(object):
            closed = False

            def sendall(self, data):
                raise SocketError

            def recv(self, num):
                raise SocketError

            def close(self):
                return

        class SocketEmpty(object):
            closed = False

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
        my_sock = Socket()
        my_chan = Channel()
        self.assertRaises(SocketSendError, server._read_forward_sock, my_sock, ChannelFailure())
        self.assertRaises(SocketError, server._read_forward_sock, SocketFailure(), my_chan)
        self.assertRaises(SocketError, server._read_channel, SocketFailure(), my_chan)
        self.assertRaises(SocketRecvError, server._read_channel, my_sock, ChannelFailure())
        my_sock.closed = True
        self.assertIsNone(server._read_forward_sock(my_sock, my_chan))
        channel = Channel()
        _socket = Socket()
        source_let = spawn(server._read_forward_sock, _socket, channel)
        dest_let = spawn(server._read_channel, _socket, channel)
        channel._eof = True
        self.assertIsNone(server._wait_send_receive_lets(source_let, dest_let, channel))
        let.kill()
