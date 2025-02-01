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

import logging
from datetime import datetime
from unittest.mock import patch

from gevent import sleep, Timeout as GTimeout, spawn
from ssh.exceptions import AuthenticationDenied

from pssh.clients.ssh.single import SSHClient, logger as ssh_logger
from pssh.exceptions import AuthenticationException, ConnectionErrorException, \
    SessionError, Timeout, \
    AuthenticationError
from .base_ssh_case import SSHTestCase

ssh_logger.setLevel(logging.DEBUG)
logging.basicConfig()


class SSHClientTest(SSHTestCase):

    def test_context_manager(self):
        with SSHClient(self.host, port=self.port,
                       pkey=self.user_key,
                       num_retries=1) as client:
            self.assertIsInstance(client, SSHClient)

    def test_pkey_from_memory(self):
        with open(self.user_key, 'rb') as fh:
            key_data = fh.read()
        SSHClient(self.host, port=self.port,
                  pkey=key_data, num_retries=1, timeout=1)

    def test_execute(self):
        host_out = self.client.run_command(self.cmd)
        output = list(host_out.stdout)
        stderr = list(host_out.stderr)
        expected = [self.resp]
        expected_stderr = []
        self.assertEqual(expected, output)
        self.assertEqual(expected_stderr, stderr)
        exit_code = host_out.channel.get_exit_status()
        self.assertEqual(exit_code, 0)

    def test_finished(self):
        self.assertFalse(self.client.finished(None))
        host_out = self.client.run_command(self.cmd)
        channel = host_out.channel
        self.assertFalse(self.client.finished(channel))
        self.assertRaises(ValueError, self.client.wait_finished, host_out.channel)
        self.client.wait_finished(host_out)
        stdout = list(host_out.stdout)
        self.assertTrue(self.client.finished(channel))
        self.assertListEqual(stdout, [self.resp])
        self.assertRaises(ValueError, self.client.wait_finished, None)
        host_out.channel = None
        self.assertIsNone(self.client.wait_finished(host_out))

    def test_finished_error(self):
        self.assertRaises(ValueError, self.client.wait_finished, None)
        self.assertIsNone(self.client.finished(None))

    def test_stderr(self):
        host_out = self.client.run_command('echo "me" >&2')
        self.client.wait_finished(host_out)
        output = list(host_out.stdout)
        stderr = list(host_out.stderr)
        expected = ['me']
        self.assertListEqual(expected, stderr)
        self.assertEqual(len(output), 0)

    def test_identity_auth(self):
        class _SSHClient(SSHClient):
            IDENTITIES = (self.user_key,)
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           timeout=1,
                           allow_agent=False)
        client._disconnect()
        client.pkey = None
        del client.session
        del client.sock
        client._connect(self.host, self.port)
        client._init_session()
        client.IDENTITIES = (self.user_key,)
        # Default identities auth only should succeed
        client._identity_auth()
        client._disconnect()
        del client.session
        del client.sock
        client._connect(self.host, self.port)
        client._init_session()
        # Auth should succeed
        self.assertIsNone(client.auth())
        # Standard init with custom identities
        client = _SSHClient(self.host, port=self.port,
                            num_retries=1,
                            allow_agent=False)
        self.assertIsInstance(client, SSHClient)

    def test_long_running_cmd(self):
        host_out = self.client.run_command('sleep .2; exit 2')
        self.assertRaises(ValueError, self.client.wait_finished, host_out.channel)
        self.client.wait_finished(host_out)
        exit_code = host_out.exit_code
        self.assertEqual(exit_code, 2)

    def test_wait_finished_timeout(self):
        host_out = self.client.run_command('sleep .2')
        timeout = .1
        self.assertFalse(self.client.finished(host_out.channel))
        start = datetime.now()
        self.assertRaises(Timeout, self.client.wait_finished, host_out, timeout=timeout)
        dt = datetime.now() - start
        self.assertTrue(timeout*1.1 > dt.total_seconds() > timeout)
        self.client.wait_finished(host_out)
        self.assertTrue(self.client.finished(host_out.channel))

    def test_client_bad_sock(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client.sock = None
        self.assertIsNone(client.poll())

    def test_multiple_clients_exec_terminates_channels(self):
        # See #200 - Multiple clients should not interfere with
        # each other. session.disconnect can leave state in library
        # and break subsequent sessions even on different socket and
        # session
        def scope_killer():
            for _ in range(20):
                client = SSHClient(self.host, port=self.port,
                                   pkey=self.user_key,
                                   num_retries=1,
                                   allow_agent=False)
                host_out = client.run_command(self.cmd)
                output = list(host_out.stdout)
                self.assertListEqual(output, [self.resp])

        scope_killer()

    def test_interactive_shell(self):
        with self.client.open_shell() as shell:
            shell.run(self.cmd)
            shell.run(self.cmd)
        stdout = list(shell.output.stdout)
        self.assertListEqual(stdout, [self.resp, self.resp])
        self.assertEqual(shell.output.exit_code, 0)

    def test_interactive_shell_exit_code(self):
        with self.client.open_shell() as shell:
            shell.run(self.cmd)
            shell.run('sleep .1')
            shell.run(self.cmd)
            shell.run('exit 1')
        stdout = list(shell.output.stdout)
        self.assertListEqual(stdout, [self.resp, self.resp])
        self.assertEqual(shell.output.exit_code, 1)

    def test_identity_auth_failure(self):
        self.assertRaises(AuthenticationException,
                          SSHClient, self.host, port=self.port, num_retries=1,
                          allow_agent=False)

    def test_password_auth_failure(self):
        try:
            SSHClient(self.host, port=self.port, num_retries=1, allow_agent=False,
                      identity_auth=False,
                      password='blah blah blah',
                      )
        except AuthenticationException as ex:
            self.assertIsInstance(ex.args[3], AuthenticationDenied)
        else:
            raise AssertionError

    def test_retry_failure(self):
        self.assertRaises(ConnectionErrorException,
                          SSHClient, self.host, port=12345,
                          timeout=1,
                          retry_delay=.1,
                          num_retries=2, _auth_thread_pool=False)

    def test_auth_retry_failure(self):
        self.assertRaises(AuthenticationException,
                          SSHClient, self.host, port=self.port,
                          user=self.user,
                          password='fake',
                          timeout=1,
                          retry_delay=.1,
                          num_retries=2,
                          allow_agent=False,
                          identity_auth=False,
                          )

    def test_connection_timeout(self):
        cmd = spawn(SSHClient, 'fakehost.com', port=12345,
                    retry_delay=.1,
                    num_retries=2, timeout=.2, _auth_thread_pool=False)
        # Should fail within greenlet timeout, otherwise greenlet will
        # raise timeout which will fail the test
        self.assertRaises(ConnectionErrorException, cmd.get, timeout=2)

    def test_open_session_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=2,
                           timeout=.1)

        def _session(timeout=None):
            sleep(.2)
        client.open_session = _session
        self.assertRaises(GTimeout, client.run_command, self.cmd)

    def test_client_read_timeout(self):
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        host_out = client.run_command('sleep 2; echo me', timeout=0.2)
        self.assertRaises(Timeout, list, host_out.stdout)

    @patch('pssh.clients.ssh.single.Session')
    def test_open_session_exc(self, mock_sess):
        class Error(Exception):
            pass

        def _session():
            raise Error

        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1)
        client._open_session = _session
        self.assertRaises(SessionError, client.open_session)

    @patch('pssh.clients.ssh.single.Session')
    def test_session_connect_exc(self, mock_sess):
        class Error(Exception):
            pass

        def _con():
            raise Error
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=2,
                           retry_delay=.2,
                           )
        client._session_connect = _con
        self.assertRaises(Error, client._init_session)

    def test_invalid_mkdir(self):
        self.assertRaises(OSError, self.client._make_local_dir, '/my_new_dir')

    def test_no_auth(self):
        self.assertRaises(
            AuthenticationError,
            SSHClient,
            self.host,
            port=self.port,
            num_retries=1,
            allow_agent=False,
            identity_auth=False,
        )

    def test_agent_auth_failure(self):
        class UnknownError(Exception):
            pass

        def _agent_auth_unk():
            raise UnknownError

        def _agent_auth_agent_err():
            raise AuthenticationDenied
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           allow_agent=True,
                           identity_auth=False)
        client.eagain(client.session.disconnect)
        client.pkey = None
        client._connect(self.host, self.port)
        client._agent_auth = _agent_auth_unk
        self.assertRaises(AuthenticationError, client.auth)
        client._agent_auth = _agent_auth_agent_err
        self.assertRaises(AuthenticationError, client.auth)

    def test_agent_auth_fake_success(self):
        def _agent_auth():
            return
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           allow_agent=True,
                           identity_auth=False)
        client.session.disconnect()
        client.pkey = None
        client._connect(self.host, self.port)
        client._agent_auth = _agent_auth
        self.assertIsNone(client.auth())

    @patch('pssh.clients.ssh.single.Session')
    def test_disconnect_exc(self, mock_sess):
        class DiscError(Exception):
            pass

        def _disc():
            raise DiscError
        client = SSHClient(self.host, port=self.port,
                           pkey=self.user_key,
                           num_retries=1,
                           retry_delay=.1,
                           )
        client._disconnect_eagain = _disc
        client._connect_init_session_retry(0)
        client._disconnect()

    def test_stdin(self):
        host_out = self.client.run_command('read line; echo $line')
        host_out.stdin.write('a line\n')
        host_out.stdin.flush()
        self.client.wait_finished(host_out)
        stdout = list(host_out.stdout)
        self.assertListEqual(stdout, ['a line'])

    def test_output_client_scope(self):
        """Output objects should keep client alive while they are in scope even if client is not."""
        def make_client_run():
            client = SSHClient(self.host, port=self.port,
                               pkey=self.user_key,
                               num_retries=1,
                               allow_agent=False,
                               )
            host_out = client.run_command("%s; exit 1" % (self.cmd,))
            return host_out

        output = make_client_run()
        stdout = list(output.stdout)
        self.assertListEqual(stdout, [self.resp])
        self.assertEqual(output.exit_code, 1)

    def test_output_client_scope_disconnect(self):
        """Forcibly disconnecting client that also goes out of scope should not break reading any unread output."""
        def make_client_run():
            client = SSHClient(self.host, port=self.port,
                               pkey=self.user_key,
                               num_retries=1,
                               allow_agent=False,
                               )
            host_out = client.run_command("%s; exit 1" % (self.cmd,))
            return host_out

        output = make_client_run()
        stdout = list(output.stdout)
        self.assertListEqual(stdout, [self.resp])
        self.assertEqual(output.exit_code, 1)
