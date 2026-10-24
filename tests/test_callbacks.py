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

from pssh.clients.base.parallel import BaseParallelSSHClient
from pssh.clients.base.single import BaseSSHClient
from pssh.output import HostOutput


class RunCommandCallbackTest(unittest.TestCase):

    def test_single_client_callback_is_stored_on_host_output(self):
        client = object.__new__(BaseSSHClient)
        client.timeout = None
        client._execute = MagicMock(return_value=object())
        host_output = HostOutput('host', None, None, client=client)
        client._make_host_output = MagicMock(return_value=host_output)
        callback = MagicMock()

        result = client.run_command(
            'echo me', callback=callback, callback_extra_args=('extra',))

        self.assertIs(result, host_output)
        self.assertIs(result.callback, callback)
        self.assertEqual(result.callback_extra_args, ('extra',))

        result.run_callback()
        result.run_callback()
        callback.assert_called_once_with(host_output, 'extra')

    def test_parallel_client_passes_callback_to_each_host(self):
        client = BaseParallelSSHClient(['host'])
        host_client = MagicMock()
        host_output = HostOutput('host', None, None, client=host_client)

        def run_command(*args, **kwargs):
            host_output.callback = kwargs['callback']
            host_output.callback_extra_args = kwargs['callback_extra_args']
            return host_output

        host_client.run_command.side_effect = run_command
        host_client.wait_finished.side_effect = lambda output, timeout=None: output.run_callback()
        client._get_ssh_client = MagicMock(return_value=host_client)
        callback = MagicMock()

        result = client.run_command(
            'echo me', callback=callback, callback_extra_args=('extra',))

        self.assertEqual(result, [host_output])
        host_client.run_command.assert_called_once_with(
            'echo me', sudo=False, user=None, shell=None,
            use_pty=False, encoding='utf-8', read_timeout=None,
            callback=callback, callback_extra_args=('extra',))
        callback.assert_not_called()

        client.join(result)
        client.join(result)
        callback.assert_called_once_with(host_output, 'extra')
