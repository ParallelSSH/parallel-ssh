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

from pssh.config import HostConfig
from pssh.exceptions import InvalidAPIUseError


class TestHostConfig(unittest.TestCase):

    def test_host_config_entries(self):
        user = 'user'
        port = 22
        password = 'password'
        alias = 'alias'
        private_key = 'private key'
        allow_agent = False
        num_retries = 1
        retry_delay = 1
        timeout = 1
        identity_auth = False
        proxy_host = 'proxy_host'
        keepalive_seconds = 1
        ipv6_only = True
        cert_file = 'file'
        auth_thread_pool = True
        forward_ssh_agent = False
        gssapi_auth = True
        gssapi_server_identity = 'some_id'
        gssapi_client_identity = 'some_id'
        gssapi_delegate_credentials = True
        compress = True
        keyboard_interactive = True
        cfg = HostConfig(
            user=user, port=port, password=password, alias=alias, private_key=private_key,
            allow_agent=allow_agent, num_retries=num_retries, retry_delay=retry_delay,
            timeout=timeout, identity_auth=identity_auth, proxy_host=proxy_host,
            ipv6_only=ipv6_only,
            keepalive_seconds=keepalive_seconds,
            cert_file=cert_file,
            auth_thread_pool=auth_thread_pool,
            forward_ssh_agent=forward_ssh_agent,
            gssapi_auth=gssapi_auth,
            gssapi_server_identity=gssapi_server_identity,
            gssapi_client_identity=gssapi_client_identity,
            gssapi_delegate_credentials=gssapi_delegate_credentials,
            compress=compress,
            keyboard_interactive=keyboard_interactive,
        )
        self.assertEqual(cfg.user, user)
        self.assertEqual(cfg.port, port)
        self.assertEqual(cfg.password, password)
        self.assertEqual(cfg.alias, alias)
        self.assertEqual(cfg.private_key, private_key)
        self.assertEqual(cfg.allow_agent, allow_agent)
        self.assertEqual(cfg.num_retries, num_retries)
        self.assertEqual(cfg.retry_delay, retry_delay)
        self.assertEqual(cfg.timeout, timeout)
        self.assertEqual(cfg.identity_auth, identity_auth)
        self.assertEqual(cfg.proxy_host, proxy_host)
        self.assertEqual(cfg.ipv6_only, ipv6_only)
        self.assertEqual(cfg.keepalive_seconds, keepalive_seconds)
        self.assertEqual(cfg.cert_file, cert_file)
        self.assertEqual(cfg.forward_ssh_agent, forward_ssh_agent)
        self.assertEqual(cfg.gssapi_auth, gssapi_auth)
        self.assertEqual(cfg.gssapi_server_identity, gssapi_server_identity)
        self.assertEqual(cfg.gssapi_client_identity, gssapi_client_identity)
        self.assertEqual(cfg.gssapi_delegate_credentials, gssapi_delegate_credentials)
        self.assertEqual(cfg.compress, compress)
        self.assertEqual(cfg.keyboard_interactive, keyboard_interactive)

    def test_host_config_bad_entries(self):
        self.assertRaises(ValueError, HostConfig, user=22)
        self.assertRaises(ValueError, HostConfig, password=22)
        self.assertRaises(ValueError, HostConfig, port='22')
        self.assertRaises(ValueError, HostConfig, alias=2)
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
        self.assertRaises(ValueError, HostConfig, ipv6_only='')
        self.assertRaises(ValueError, HostConfig, keepalive_seconds='')
        self.assertRaises(ValueError, HostConfig, cert_file=1)
        self.assertRaises(ValueError, HostConfig, forward_ssh_agent='')
        self.assertRaises(ValueError, HostConfig, gssapi_auth='')
        self.assertRaises(ValueError, HostConfig, gssapi_server_identity=1)
        self.assertRaises(ValueError, HostConfig, gssapi_client_identity=1)
        self.assertRaises(ValueError, HostConfig, gssapi_delegate_credentials='')
        self.assertRaises(ValueError, HostConfig, compress='')
        self.assertRaises(ValueError, HostConfig, password='fake', keyboard_interactive='')
        self.assertRaises(InvalidAPIUseError, HostConfig, keyboard_interactive=True)
