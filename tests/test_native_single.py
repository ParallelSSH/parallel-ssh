#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.


"""Regression tests for the native/libssh2 single-client lifecycle."""


import unittest

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

    def test_wait_finished_waits_for_close_before_exit_status(self):
        client = object.__new__(SSHClient)
        client.eagain = lambda func: func()
        client.close_channel = lambda channel: client.eagain(channel.close)
        channel = Channel()
        output = HostOutput('host', channel, None, client=client)

        client.wait_finished(output)

        self.assertEqual(channel.calls, ['wait_eof', 'close', 'wait_closed'])
        self.assertEqual(output.exit_code, 0)
