#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.


"""Regression tests for the native/libssh2 single-client lifecycle."""


import unittest
from unittest.mock import Mock, call, patch

from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from pssh.clients.native.single import SSHClient
from pssh.exceptions import SCPError, SFTPError
from pssh.output import HostOutput


class Channel:

    def __init__(self):
        self.calls = []
        self.closed = False

    def wait_eof(self):
        self.calls.append('wait_eof')

    def close(self):
        self.calls.append('close')

    def wait_closed(self):
        self.calls.append('wait_closed')
        self.closed = True

    def eof(self):
        return self.closed

    def get_exit_status(self):
        return 0


class NativeSingleClientTest(unittest.TestCase):

    @patch('pssh.clients.native.single.FileObjectThread')
    def test_scp_recv_rejects_unexpected_eof(self, file_object):
        client = object.__new__(SSHClient)
        client.host = '127.0.0.1'
        client.session = Mock()
        client.poll = Mock()
        channel = Mock()
        channel.read.return_value = (0, b'')
        channel.eof.return_value = True
        fileinfo = Mock(st_size=4)
        client.session.scp_recv2.return_value = (channel, fileinfo)

        with self.assertRaises(SCPError):
            client._scp_recv('remote', 'local')

        channel.read.assert_called_once_with(size=4)
        client.poll.assert_not_called()
        file_object.return_value.write.assert_not_called()
        file_object.return_value.flush.assert_called_once_with()
        file_object.return_value.close.assert_called_once_with()
        channel.close.assert_called_once_with()

    @patch('pssh.clients.native.single.sleep')
    @patch('pssh.clients.native.single.FileObjectThread')
    def test_scp_recv_waits_on_empty_read_before_eof(self, file_object, sleep):
        client = object.__new__(SSHClient)
        client.host = '127.0.0.1'
        client.session = Mock()
        client.poll = Mock()
        channel = Mock()
        channel.read.side_effect = [(0, b''), (4, b'data')]
        channel.eof.return_value = False
        fileinfo = Mock(st_size=4)
        client.session.scp_recv2.return_value = (channel, fileinfo)

        client._scp_recv('remote', 'local')

        self.assertEqual(channel.read.call_count, 2)
        client.poll.assert_called_once_with()
        sleep.assert_called_once_with(.1)
        file_object.return_value.write.assert_called_once_with(b'data')
        channel.close.assert_called_once_with()

    @patch('pssh.clients.native.single.sleep')
    @patch('pssh.clients.native.single.monotonic')
    @patch('pssh.clients.native.single.FileObjectThread')
    def test_scp_recv_fails_when_empty_reads_stall_without_eof(
            self, file_object, monotonic, sleep):
        # libssh2 returns 0 bytes without EOF when the remote closes the
        # channel without sending EOF.
        client = object.__new__(SSHClient)
        client.host = '127.0.0.1'
        client.session = Mock()
        client.poll = Mock()
        channel = Mock()
        channel.read.return_value = (0, b'')
        channel.eof.return_value = False
        fileinfo = Mock(st_size=4)
        client.session.scp_recv2.return_value = (channel, fileinfo)
        monotonic.side_effect = [0, 10, client._SCP_RECV_STALL_TIMEOUT + 1]

        with self.assertRaises(SCPError):
            client._scp_recv('remote', 'local')

        self.assertEqual(channel.read.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(.1), call(.1)])
        file_object.return_value.write.assert_not_called()
        file_object.return_value.close.assert_called_once_with()
        channel.close.assert_called_once_with()

    @patch('pssh.clients.native.single.sleep')
    @patch('pssh.clients.native.single.monotonic')
    @patch('pssh.clients.native.single.FileObjectThread')
    def test_scp_recv_progress_resets_stall_timer(
            self, file_object, monotonic, sleep):
        client = object.__new__(SSHClient)
        client.host = '127.0.0.1'
        client.session = Mock()
        client.poll = Mock()
        channel = Mock()
        channel.read.side_effect = [
            (0, b''), (2, b'da'), (0, b''), (LIBSSH2_ERROR_EAGAIN, b''),
            (0, b''), (2, b'ta')]
        channel.eof.return_value = False
        fileinfo = Mock(st_size=4)
        client.session.scp_recv2.return_value = (channel, fileinfo)
        stall = client._SCP_RECV_STALL_TIMEOUT
        # Each empty read would exceed the limit if the stall timer were
        # carried over across received data or EAGAIN.
        monotonic.side_effect = [0, stall + 1, 2 * stall + 2]

        client._scp_recv('remote', 'local')

        self.assertEqual(channel.read.call_count, 6)
        file_object.return_value.write.assert_has_calls(
            [call(b'da'), call(b'ta')])
        channel.close.assert_called_once_with()

    @patch('pssh.clients.native.single.FileObjectThread')
    def test_scp_recv_limits_read_size_to_buffer(self, file_object):
        client = object.__new__(SSHClient)
        client._SCP_RECV_BUF_SIZE = 3
        client.session = Mock()
        client.poll = Mock()
        channel = Mock()
        channel.read.side_effect = [(3, b'one'), (1, b'!')]
        fileinfo = Mock(st_size=4)
        client.session.scp_recv2.return_value = (channel, fileinfo)

        client._scp_recv('remote', 'local')

        self.assertEqual(channel.read.call_args_list,
                         [call(size=3), call(size=1)])
        client.poll.assert_not_called()
        file_object.return_value.write.assert_has_calls([call(b'one'), call(b'!')])

    def test_public_factory_returns_sftp_wrapper(self):
        from pssh.clients.native.sftp import SFTPClient
        client = object.__new__(SSHClient)
        raw = Mock()
        raw.realpath.return_value = '/home/test'
        client.eagain = lambda func, *args: func(*args)
        client._make_sftp = lambda: raw
        result = client.make_sftp_client()
        self.assertIsInstance(result, SFTPClient)
        self.assertIs(result._sftp, raw)

    def test_private_factory_returns_channel_and_wraps_errors(self):
        client = object.__new__(SSHClient)
        sftp = object()
        client._make_sftp_eagain = lambda: sftp

        self.assertIs(client._make_sftp(), sftp)

        error = RuntimeError('sftp init failed')

        def raise_error():
            raise error

        client._make_sftp_eagain = raise_error

        with self.assertRaises(SFTPError) as raised:
            client._make_sftp()

        self.assertIs(raised.exception.args[0], error)

    def test_transfer_helpers_create_sftp_client(self):
        client = Mock(spec=SSHClient)
        client.host = 'host'
        sftp = Mock()
        client._make_sftp.return_value = sftp
        client._remote_paths_split.return_value = None
        client._sftp_openfh.side_effect = SFTPError
        client._scp_recv_recursive.return_value = 'received'
        client._scp_send_dir.return_value = 'sent'
        client.eagain.side_effect = lambda func, *args: func(*args)

        with patch('pssh.clients.native.single.os.path.isdir') as isdir:
            isdir.return_value = False
            SSHClient.copy_file(client, 'local', 'remote')
            SSHClient.copy_remote_file(client, 'remote', 'local')
            self.assertEqual(
                SSHClient.scp_recv(
                    client, 'remote', 'local', recurse=True), 'received')
            isdir.return_value = True
            self.assertEqual(
                SSHClient.scp_send(
                    client, 'local', 'remote', recurse=True), 'sent')
            isdir.return_value = False
            client._remote_paths_split.return_value = '/remote'
            SSHClient.scp_send(
                client, 'local', 'remote/file', recurse=True)

        self.assertEqual(client._make_sftp.call_count, 5)

    def test_wait_finished_waits_for_close_before_exit_status(self):
        client = object.__new__(SSHClient)
        client.eagain = lambda func: func()
        client.close_channel = lambda channel: client.eagain(channel.close)
        channel = Channel()
        output = HostOutput('host', channel, None, client=client)

        client.wait_finished(output)

        self.assertEqual(channel.calls, ['wait_eof', 'close', 'wait_closed'])
        self.assertEqual(output.exit_code, 0)
