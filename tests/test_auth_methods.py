#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.


"""Authentication is attempted only with methods the server allows - #265."""


import unittest

from pssh.clients.native.single import SSHClient as NativeSSHClient
from pssh.clients.ssh.single import SSHClient as LibSSHClient
from pssh.exceptions import AuthenticationError


class NativeSession:
    """Fake libssh2 session. ``methods`` is the userauth_list result, or a list of them
    returned in turn on each call."""

    def __init__(self, methods, authenticated=False, agent_ok=False, none_ok=False):
        self._methods = methods
        self._authenticated = authenticated
        self._none_ok = none_ok
        self._agent_ok = agent_ok
        self.calls = []

    def userauth_list(self, user):
        self.calls.append('list')
        if self._none_ok:
            # libssh2 requests ``none`` auth to get the list, which the server may accept.
            self._authenticated = True
            return None
        if self._methods and isinstance(self._methods[0], list):
            return self._methods.pop(0) if len(self._methods) > 1 else self._methods[0]
        return self._methods

    def userauth_authenticated(self):
        return self._authenticated

    def agent_auth(self, user):
        self.calls.append('agent')
        if not self._agent_ok:
            raise Exception("agent auth failed")

    def userauth_publickey_frommemory(self, user, pkey_data, passphrase=b''):
        self.calls.append('pkey')

    def userauth_password(self, user, password):
        self.calls.append('password')

    def userauth_keyboardinteractive(self, user, password):
        self.calls.append('keyboard-interactive')


class LibSSHSession:
    """Fake libssh session. ``flags`` is the SSH_AUTH_METHOD_* bitmask from userauth_list."""

    def __init__(self, flags, none_ok=False):
        self._flags = flags
        self._none_ok = none_ok
        self.calls = []

    def userauth_none(self):
        self.calls.append('none')
        if not self._none_ok:
            raise Exception("denied")
        return 0

    def userauth_list(self):
        self.calls.append('list')
        return self._flags

    def userauth_agent(self, user):
        self.calls.append('agent')
        raise Exception("agent auth failed")

    def userauth_password(self, user, password):
        self.calls.append('password')


def make_client(cls, session, password='pass', allow_agent=True, pkey=None,
                keyboard_interactive=False):
    client = object.__new__(cls)
    client.session = session
    client.user = 'user'
    client.password = password
    client.pkey = pkey
    client.allow_agent = allow_agent
    client.identity_auth = False
    client.keyboard_interactive = keyboard_interactive
    client.gssapi_auth = False
    client.gssapi_server_identity = None
    client.gssapi_client_identity = None
    return client


class NativeAuthMethodsTest(unittest.TestCase):

    def test_password_only_server_skips_public_key_methods(self):
        session = NativeSession(['password'])
        make_client(NativeSSHClient, session).auth()
        self.assertEqual(session.calls, ['list', 'password'])

    def test_public_key_only_server_does_not_try_password(self):
        session = NativeSession(['publickey'])
        client = make_client(NativeSSHClient, session, allow_agent=False)
        self.assertRaises(AuthenticationError, client.auth)
        self.assertNotIn('password', session.calls)

    def test_unknown_methods_keep_previous_behaviour(self):
        session = NativeSession(None)
        make_client(NativeSSHClient, session).auth()
        self.assertEqual(session.calls, ['list', 'agent', 'list', 'password'])

    def test_server_accepting_none_auth_needs_no_credentials(self):
        session = NativeSession(None, none_ok=True)
        make_client(NativeSSHClient, session).auth()
        self.assertEqual(session.calls, ['list'])

    def test_stale_authenticated_flag_is_not_none_auth(self):
        session = NativeSession(None, authenticated=True)
        make_client(NativeSSHClient, session).auth()
        self.assertEqual(session.calls, ['list', 'agent', 'list', 'password'])

    def test_pkey_with_password_only_server_raises_without_trying_key(self):
        session = NativeSession(['password'])
        client = make_client(NativeSSHClient, session, pkey=b'key data')
        self.assertRaises(AuthenticationError, client.auth)
        self.assertNotIn('pkey', session.calls)

    def test_pkey_with_public_key_server_is_attempted(self):
        session = NativeSession(['publickey', 'password'])
        make_client(NativeSSHClient, session, pkey=b'key data').auth()
        self.assertEqual(session.calls, ['list', 'pkey'])

    def test_keyboard_interactive_follows_server_list(self):
        session = NativeSession(['publickey', 'keyboard-interactive'])
        make_client(NativeSSHClient, session, allow_agent=False,
                    keyboard_interactive=True).auth()
        self.assertEqual(session.calls, ['list', 'keyboard-interactive'])
        session = NativeSession(['publickey', 'keyboard-interactive'])
        client = make_client(NativeSSHClient, session, allow_agent=False)
        self.assertRaises(AuthenticationError, client.auth)
        self.assertNotIn('password', session.calls)

    def test_methods_are_retrieved_again_after_a_failed_attempt(self):
        session = NativeSession([['publickey', 'password'], ['password']])
        make_client(NativeSSHClient, session).auth()
        self.assertEqual(session.calls, ['list', 'agent', 'list', 'password'])

    def test_successful_agent_auth_stops(self):
        session = NativeSession(['publickey', 'password'], agent_ok=True)
        make_client(NativeSSHClient, session).auth()
        self.assertEqual(session.calls, ['list', 'agent'])

    def test_error_names_the_methods_the_server_allows(self):
        session = NativeSession(['publickey', 'keyboard-interactive'])
        client = make_client(NativeSSHClient, session, allow_agent=False)
        with self.assertRaises(AuthenticationError) as cm:
            client.auth()
        self.assertIn('keyboard-interactive, publickey', cm.exception.args)


class LibSSHAuthMethodsTest(unittest.TestCase):

    def test_flags_are_mapped_to_method_names(self):
        session = LibSSHSession(0x0002 | 0x0004 | 0x0010)
        client = make_client(LibSSHClient, session)
        self.assertEqual(client._auth_methods(),
                         {'password', 'publickey', 'keyboard-interactive'})
        self.assertEqual(session.calls, ['none', 'list'])

    def test_none_auth_is_requested_only_once(self):
        session = LibSSHSession(0x0002)
        client = make_client(LibSSHClient, session)
        client._auth_methods()
        client._auth_methods()
        self.assertEqual(session.calls, ['none', 'list', 'list'])

    def test_password_only_server_skips_agent(self):
        session = LibSSHSession(0x0002)
        make_client(LibSSHClient, session).auth()
        self.assertEqual(session.calls, ['none', 'list', 'password'])

    def test_public_key_only_server_does_not_try_password(self):
        session = LibSSHSession(0x0004)
        client = make_client(LibSSHClient, session, allow_agent=False)
        self.assertRaises(AuthenticationError, client.auth)
        self.assertNotIn('password', session.calls)

    def test_server_accepting_none_auth_needs_no_credentials(self):
        session = LibSSHSession(0, none_ok=True)
        make_client(LibSSHClient, session).auth()
        self.assertEqual(session.calls, ['none'])

    def test_unknown_methods_keep_previous_behaviour(self):
        session = LibSSHSession(0)
        make_client(LibSSHClient, session).auth()
        self.assertEqual(session.calls, ['none', 'list', 'agent', 'list', 'password'])
