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

from pssh.config import HostConfig

class TestHostConfig(unittest.TestCase):

    def test_host_config_entries(self):
        user='user'
        port=22
        password='password'
        private_key='private key'
        allow_agent=False
        num_retries=1
        retry_delay=1
        timeout=1
        identity_auth=False
        proxy_host='proxy_host'
        keepalive_seconds=1
        cfg = HostConfig(
            user=user, port=port, password=password, private_key=private_key,
            allow_agent=allow_agent, num_retries=num_retries, retry_delay=retry_delay,
            timeout=timeout, identity_auth=identity_auth, proxy_host=proxy_host)
        self.assertEqual(cfg.user, user)
        self.assertEqual(cfg.port, port)
        self.assertEqual(cfg.password, password)
        self.assertEqual(cfg.private_key, private_key)
        self.assertEqual(cfg.allow_agent, allow_agent)
        self.assertEqual(cfg.num_retries, num_retries)
        self.assertEqual(cfg.retry_delay, retry_delay)
        self.assertEqual(cfg.timeout, timeout)
        self.assertEqual(cfg.identity_auth, identity_auth)
        self.assertEqual(cfg.proxy_host, proxy_host)

    def test_host_config_bad_entries(self):
        self.assertRaises(ValueError, HostConfig, user=22)
        self.assertRaises(ValueError, HostConfig, password=22)
        self.assertRaises(ValueError, HostConfig, port='22')
        self.assertRaises(ValueError, HostConfig, private_key=1)
        self.assertRaises(ValueError, HostConfig, allow_agent=1)
        self.assertRaises(ValueError, HostConfig, num_retries='')
        self.assertRaises(ValueError, HostConfig, retry_delay='')
        self.assertRaises(ValueError, HostConfig, timeout='')
        self.assertRaises(ValueError, HostConfig, identity_auth='')
        self.assertRaises(ValueError, HostConfig, proxy_host=1)
        self.assertRaises(ValueError, HostConfig, proxy_port='')
        self.assertRaises(ValueError, HostConfig, proxy_user=1)
        self.assertRaises(ValueError, HostConfig, proxy_password=1)
        self.assertRaises(ValueError, HostConfig, proxy_pkey=1)
        self.assertRaises(ValueError, HostConfig, keepalive_seconds='')
