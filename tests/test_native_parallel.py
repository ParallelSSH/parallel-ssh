#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.

from unittest import TestCase
from unittest.mock import Mock, call, patch

from gevent import Timeout

from pssh.clients.native import ParallelSFTPClient
from pssh.clients.native import parallel


class DeferredTask:

    def __init__(self, func, *args):
        self.func = func
        self.args = args

    def get(self):
        return self.func(*self.args)


class RecordingPool:

    def __init__(self):
        self.calls = []

    def spawn(self, func, *args):
        self.calls.append(args)
        return DeferredTask(func, *args)


class ParallelSFTPClientTest(TestCase):

    def make_client(self, hosts, host_clients):
        client = Mock()
        client.hosts = hosts
        client.pool = RecordingPool()
        client._get_ssh_client = Mock(
            side_effect=lambda host_i, _host: host_clients[host_i])
        client._make_sftp_client = ParallelSFTPClient._make_sftp_client.__get__(
            client)
        client._get_sftp_client = ParallelSFTPClient._get_sftp_client.__get__(
            client)
        client._collect = ParallelSFTPClient._collect
        client._sftp_clients = {}
        return client

    @patch.object(parallel, 'SFTPClient')
    def test_connect_creates_sftp_clients_in_host_order(self, sftp_client):
        hosts = ['host-b', 'host-a', 'host-c']
        host_clients = [Mock(name=host) for host in hosts]
        sftp_clients = [Mock(name='%s-sftp' % host) for host in hosts]
        sftp_client.side_effect = sftp_clients
        client = self.make_client(hosts, host_clients)

        result = ParallelSFTPClient.connect(client)

        self.assertEqual(sftp_clients, result)
        self.assertEqual([(0, 'host-b'), (1, 'host-a'), (2, 'host-c')],
                         client.pool.calls)
        self.assertEqual([call(host_client) for host_client in host_clients],
                         sftp_client.call_args_list)

        self.assertEqual(sftp_clients, ParallelSFTPClient.connect(client))
        self.assertEqual(len(hosts), sftp_client.call_count)

    @patch.object(parallel, 'SFTPClient')
    def test_connect_returns_errors_in_host_order_when_not_stopping(self,
                                                                    sftp_client):
        hosts = ['first', 'failing', 'last']
        host_clients = [Mock(name=host) for host in hosts]
        first = Mock(name='first-sftp')
        error = RuntimeError('SFTP unavailable')
        last = Mock(name='last-sftp')
        sftp_client.side_effect = [first, error, last]
        client = self.make_client(hosts, host_clients)

        result = ParallelSFTPClient.connect(client, stop_on_errors=False)

        self.assertEqual([first, error, last], result)

    @patch.object(parallel, 'SFTPClient')
    def test_connect_raises_when_stopping_on_errors(self, sftp_client):
        error = RuntimeError('SFTP unavailable')
        sftp_client.side_effect = [Mock(name='first-sftp'), error]
        client = self.make_client(
            ['first', 'failing'], [Mock(name='first'), Mock(name='failing')])

        with self.assertRaisesRegex(RuntimeError, 'SFTP unavailable'):
            ParallelSFTPClient.connect(client, stop_on_errors=True)

    @patch.object(parallel, 'SFTPClient')
    def test_operations_run_for_every_host_and_preserve_result_order(
            self, sftp_client):
        hosts = ['host-b', 'host-a']
        host_clients = [Mock(name=host) for host in hosts]
        sftp_clients = [Mock(name='%s-sftp' % host) for host in hosts]
        sftp_client.side_effect = sftp_clients
        client = self.make_client(hosts, host_clients)
        client._run_sftp_operation = \
            ParallelSFTPClient._run_sftp_operation.__get__(client)
        client._run_parallel = ParallelSFTPClient._run_parallel.__get__(client)
        sftp_clients[0].listdir.return_value = iter(['b-one', 'b-two'])
        sftp_clients[1].listdir.return_value = iter(['a-one'])

        result = ParallelSFTPClient.listdir(client, 'data')

        self.assertEqual([['b-one', 'b-two'], ['a-one']], result)
        self.assertEqual(
            [call('data', 'utf-8'), call('data', 'utf-8')],
            [sftp.listdir.call_args for sftp in sftp_clients],
        )
        self.assertEqual(len(hosts), sftp_client.call_count)

        self.assertEqual(
            [sftp.getcwd.return_value for sftp in sftp_clients],
            ParallelSFTPClient.getcwd(client),
        )
        self.assertEqual(len(hosts), sftp_client.call_count)

    @patch.object(parallel, 'SFTPClient')
    def test_operation_errors_follow_stop_on_errors(self, sftp_client):
        hosts = ['first', 'failing', 'last']
        sftp_clients = [Mock(name='%s-sftp' % host) for host in hosts]
        error = RuntimeError('stat unavailable')
        sftp_clients[0].stat.return_value = 'first-stat'
        sftp_clients[1].stat.side_effect = error
        sftp_clients[2].stat.return_value = 'last-stat'
        sftp_client.side_effect = sftp_clients
        client = self.make_client(hosts, [Mock(name=host) for host in hosts])
        client._run_sftp_operation = \
            ParallelSFTPClient._run_sftp_operation.__get__(client)
        client._run_parallel = ParallelSFTPClient._run_parallel.__get__(client)

        result = ParallelSFTPClient.stat(
            client, 'target', stop_on_errors=False)

        self.assertEqual(['first-stat', error, 'last-stat'], result)

        with self.assertRaisesRegex(RuntimeError, 'stat unavailable'):
            ParallelSFTPClient.stat(client, 'target')

    def test_collect_can_return_gevent_timeout(self):
        timeout = Timeout(1)

        def raise_timeout():
            raise timeout

        result = ParallelSFTPClient._collect(
            [DeferredTask(raise_timeout)], stop_on_errors=False)

        self.assertEqual([timeout], result)

    def test_public_operations_forward_arguments(self):
        client = Mock()
        operations = [
            ('chdir', ('directory',), ('chdir', ('directory',))),
            ('stat', ('file',), ('stat', ('file',))),
            ('lstat', ('link',), ('lstat', ('link',))),
            ('mkdir', ('directory',), ('mkdir', ('directory',))),
            ('rmdir', ('directory',), ('rmdir', ('directory',))),
            ('rename', ('old', 'new'), ('rename', ('old', 'new'))),
            ('remove', ('file',), ('remove', ('file',))),
            ('unlink', ('file',), ('remove', ('file',))),
            ('get', ('remote', 'local'), ('get', ('remote', 'local'))),
            ('put', ('local', 'remote'), ('put', ('local', 'remote'))),
        ]

        for method, args, forwarded in operations:
            with self.subTest(method=method):
                getattr(ParallelSFTPClient, method)(client, *args)
                client._run_parallel.assert_called_once_with(
                    forwarded[0], forwarded[1], stop_on_errors=True)
                client._run_parallel.reset_mock()

    def test_changing_hosts_invalidates_sftp_clients(self):
        client = object.__new__(ParallelSFTPClient)
        client._hosts = ['old-host']
        client._host_clients = {(0, 'old-host'): Mock()}
        client._sftp_clients = {(0, 'old-host'): Mock()}

        client.hosts = ['new-host']

        self.assertEqual({}, client._host_clients)
        self.assertEqual({}, client._sftp_clients)
