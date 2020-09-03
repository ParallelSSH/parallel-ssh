# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2020 Panos Kittenis
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
from logging import NullHandler

from pssh import utils

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
        utils.logger.handlers = [NullHandler()]
