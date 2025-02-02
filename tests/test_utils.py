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

import unittest

from unittest.mock import MagicMock
from logging import NullHandler, DEBUG

from pssh import utils
from pssh.clients.base.single import PollMixIn


class ParallelSSHUtilsTest(unittest.TestCase):

    def test_enabling_host_logger(self):
        self.assertTrue(len([h for h in utils.host_logger.handlers
                             if isinstance(h, NullHandler)]) == 1)
        utils.enable_host_logger()
        # And again to test only one non-null handler is attached
        utils.enable_host_logger()
        self.assertTrue(len([h for h in utils.host_logger.handlers
                             if not isinstance(h, NullHandler)]) == 1)
        utils.host_logger.handlers = [NullHandler()]

    def test_enabling_pssh_logger(self):
        self.assertTrue(len([h for h in utils.logger.handlers
                             if isinstance(h, NullHandler)]) == 1)
        utils.enable_logger(utils.logger)
        utils.enable_logger(utils.logger)
        self.assertTrue(len([h for h in utils.logger.handlers
                             if not isinstance(h, NullHandler)]) == 1)
        utils.enable_debug_logger()
        self.assertEqual(utils.logger.level, DEBUG)
        utils.logger.handlers = [NullHandler()]

    def test_poll_mixin(self):
        my_sock = MagicMock()
        mixin = PollMixIn(my_sock)
        directions_func = MagicMock()
        directions_func.return_value = 0
        self.assertEqual(mixin.sock, my_sock)
        self.assertIsNone(mixin._poll_errcodes(directions_func, 1, 1))
