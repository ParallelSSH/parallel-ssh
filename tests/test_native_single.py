#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.


"""Regression tests for the native/libssh2 single-client lifecycle."""


import unittest

from gevent import Greenlet, sleep
from gevent.event import Event

from pssh.clients.native.single import SSHClient
from pssh.exceptions import Timeout
from pssh.output import BufferData, HostOutput, HostOutputBuffers


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

    def test_wait_finished_waits_for_close_before_exit_status(self):
        client = object.__new__(SSHClient)
        client.eagain = lambda func: func()
        client.close_channel = lambda channel: client.eagain(channel.close)
        channel = Channel()
        output = HostOutput('host', channel, None, client=client)

        client.wait_finished(output)

        self.assertEqual(channel.calls, ['wait_eof', 'close', 'wait_closed'])
        self.assertEqual(output.exit_code, 0)

    def _client(self):
        client = object.__new__(SSHClient)
        client.eagain = lambda func: func()
        client.close_channel = lambda channel: client.eagain(channel.close)
        return client

    def _output(self, client, channel, stdout_reader, stderr_reader):
        stdout_reader.start()
        stderr_reader.start()
        buffers = HostOutputBuffers(
            stdout=BufferData(reader=stdout_reader, rw_buffer=None),
            stderr=BufferData(reader=stderr_reader, rw_buffer=None))
        return HostOutput('host', channel, None, client=client, buffers=buffers)

    def test_wait_finished_drains_queued_output_before_exit_status(self):
        # libssh2 reports no EOF while output is still queued on the channel,
        # even after the remote close handshake.
        client = self._client()
        channel = Channel()
        channel.queued = {'stdout', 'stderr'}
        channel.eof = lambda: channel.closed and not channel.queued

        def drain(stream, yields):
            for _ in range(yields):
                sleep(0)
            channel.calls.append('drain ' + stream)
            channel.queued.discard(stream)

        # stderr finishes last, so both readers must be waited on.
        output = self._output(
            client, channel,
            Greenlet(drain, 'stdout', 0), Greenlet(drain, 'stderr', 3))

        client.wait_finished(output)

        self.assertEqual(
            channel.calls,
            ['wait_eof', 'close', 'wait_closed', 'drain stdout', 'drain stderr'])
        self.assertEqual(output.exit_code, 0)

    def test_wait_finished_timeout_covers_output_readers(self):
        client = self._client()
        channel = Channel()
        stuck = Event()
        output = self._output(
            client, channel, Greenlet(stuck.wait), Greenlet(lambda: None))

        self.assertRaises(Timeout, client.wait_finished, output, timeout=.1)
        self.assertEqual(channel.calls, ['wait_eof', 'close', 'wait_closed'])
