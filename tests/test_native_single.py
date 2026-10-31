#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.


"""Regression tests for the native/libssh2 single-client lifecycle."""


import os
import unittest

from gevent import socket

from pssh.clients.native.single import SSHClient
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

    def assert_disconnect_closes_descriptor(self, sock):
        client = object.__new__(SSHClient)
        client.sock = sock
        client.session = None
        client._proxy_client = None
        descriptor = sock.fileno()
        try:
            client._disconnect()
            self.assertIsNone(client.sock)
            self.assertTrue(sock.closed)
            self.assertRaises(OSError, os.fstat, descriptor)
            client._disconnect()
        finally:
            client.sock = None
            if not sock.closed:
                sock.close()
            else:
                # Reclaim an fd detached by a failing implementation.
                try:
                    os.fstat(descriptor)
                except OSError:
                    pass
                else:
                    os.close(descriptor)

    def test_disconnect_closes_socket_descriptor(self):
        sock, peer = socket.socketpair()
        try:
            self.assert_disconnect_closes_descriptor(sock)
        finally:
            peer.close()

    def test_disconnect_closes_socket_when_shutdown_fails(self):
        self.assert_disconnect_closes_descriptor(socket.socket())

    def test_wait_finished_waits_for_close_before_exit_status(self):
        client = object.__new__(SSHClient)
        client.eagain = lambda func: func()
        client.close_channel = lambda channel: client.eagain(channel.close)
        channel = Channel()
        output = HostOutput('host', channel, None, client=client)

        client.wait_finished(output)

        self.assertEqual(channel.calls, ['wait_eof', 'close', 'wait_closed'])
        self.assertEqual(output.exit_code, 0)
