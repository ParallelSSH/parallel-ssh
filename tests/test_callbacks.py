#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.


"""Tests for run_command completion callbacks."""


import unittest
from unittest.mock import MagicMock

from gevent.event import Event
from gevent.hub import sleep

from pssh.clients.base.parallel import BaseParallelSSHClient
from pssh.clients.base.single import BaseSSHClient
from pssh.output import HostOutput


class RunCommandCallbackTest(unittest.TestCase):

    def test_single_client_callback_waits_for_completion(self):
        client = object.__new__(BaseSSHClient)
        client.timeout = None
        client._execute = MagicMock(return_value=object())
        client.wait_finished = MagicMock()
        host_output = HostOutput('host', None, None, client=client)
        client._make_host_output = MagicMock(return_value=host_output)
        callback_called = Event()
        callback_args = []

        def callback(output, extra):
            callback_args.extend((output, extra))
            callback_called.set()

        result = client.run_command(
            'echo me', callback=callback, callback_extra_args=('extra',))

        self.assertIs(result, host_output)
        self.assertTrue(callback_called.wait(timeout=1))
        client.wait_finished.assert_called_once_with(host_output)
        self.assertEqual(callback_args, [host_output, 'extra'])

    def test_parallel_client_callback_runs_for_each_host(self):
        client = BaseParallelSSHClient(['host'])
        host_client = MagicMock()
        host_output = HostOutput('host', None, None, client=host_client)
        client._run_command = MagicMock(return_value=host_output)
        callback_called = Event()
        callback_args = []

        def callback(output, extra):
            callback_args.extend((output, extra))
            callback_called.set()

        result = client.run_command(
            'echo me', callback=callback, callback_extra_args=('extra',))

        self.assertEqual(result, [host_output])
        self.assertTrue(callback_called.wait(timeout=1))
        host_client.wait_finished.assert_called_once_with(host_output)
        self.assertEqual(callback_args, [host_output, 'extra'])

        # Give spawned greenlets a chance to finish before the test tears down.
        sleep(0)
