#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.

"""Regression tests for the ssh-python single-client lifecycle."""

import unittest
from unittest.mock import MagicMock, patch

from gevent import spawn

from pssh.clients.ssh.single import SSHClient
from pssh.exceptions import SessionError
from pssh.output import HostOutput, BufferData, HostOutputBuffers


class SSHSingleClientTest(unittest.TestCase):

    @patch('pssh.clients.ssh.single.Event')
    def test_wait_finished_closes_after_status_without_remote_close(self, event):
        # This server has sent status, but will only close after the client.
        channel = MagicMock()
        channel.get_exit_status.return_value = 23
        channel.is_closed.return_value = False
        channel.is_eof.return_value = True
        event.return_value.dopoll.return_value = 0
        client = object.__new__(SSHClient)
        client.sock = None
        client.session = MagicMock()
        client.session.is_connected.return_value = True
        client.eagain = lambda func: func()
        output = HostOutput(
            'host', channel, None, client=client,
            buffers=HostOutputBuffers(
                BufferData(spawn(lambda: None), None),
                BufferData(spawn(lambda: None), None)))

        client.wait_finished(output, timeout=1)

        self.assertEqual(output.exit_code, 23)
        channel.close.assert_called_once_with()
        self.assertFalse(channel.is_closed())

    @patch('pssh.clients.ssh.single.Event')
    def test_wait_finished_polls_delayed_status_before_local_close(self, event):
        channel = MagicMock()
        channel.get_exit_status.side_effect = [-1, -1, 23, 23]
        channel.is_closed.return_value = False
        channel.is_eof.return_value = True
        event.return_value.dopoll.return_value = 0
        client = object.__new__(SSHClient)
        client.sock = None
        client.session = MagicMock()
        client.session.is_connected.return_value = True
        client.eagain = lambda func: func()
        output = HostOutput(
            'host', channel, None, client=client,
            buffers=HostOutputBuffers(
                BufferData(spawn(lambda: None), None),
                BufferData(spawn(lambda: None), None)))

        client.wait_finished(output, timeout=1)

        self.assertEqual(output.exit_code, 23)
        channel.close.assert_called_once_with()
        self.assertEqual(event.return_value.dopoll.call_count, 2)
        self.assertEqual(event.return_value.remove_session.call_count, 2)

    @patch('pssh.clients.ssh.single.Event')
    def test_packet_processing_error_detaches_session(self, event):
        channel = MagicMock()
        channel.get_exit_status.return_value = -1
        channel.is_closed.return_value = False
        event.return_value.dopoll.return_value = -1
        client = object.__new__(SSHClient)
        client.sock = None
        client.session = MagicMock()
        client.session.is_connected.return_value = True

        with self.assertRaises(SessionError):
            client._wait_exit_status(channel)

        event.return_value.remove_session.assert_called_once_with(client.session)
        channel.close.assert_not_called()
