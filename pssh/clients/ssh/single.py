# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2020 Panos Kittenis.
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

from gevent import sleep, spawn, Timeout as GTimeout, joinall
from ssh import options
from ssh.session import Session, SSH_READ_PENDING, SSH_WRITE_PENDING
from ssh.key import import_privkey_file, import_cert_file, copy_cert_to_privkey,\
    import_privkey_base64
from ssh.exceptions import EOF
from ssh.error_codes import SSH_AGAIN

from ..base.single import BaseSSHClient
from ..common import _validate_pkey_path
from ...output import HostOutput
from ...exceptions import SessionError, Timeout
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)


class SSHClient(BaseSSHClient):
    """ssh-python based non-blocking client."""

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 cert_file=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 identity_auth=True,
                 gssapi_auth=False,
                 gssapi_server_identity=None,
                 gssapi_client_identity=None,
                 gssapi_delegate_credentials=False,
                 ipv6_only=False,
                 _auth_thread_pool=True):
        """:param host: Host name or IP to connect to.
        :type host: str
        :param user: User to connect as. Defaults to logged in user.
        :type user: str
        :param password: Password to use for password authentication.
        :type password: str
        :param port: SSH port to connect to. Defaults to SSH default (22)
        :type port: int
        :param pkey: Private key file path to use for authentication. Path must
          be either absolute path or relative to user home directory
          like ``~/<path>``.
          Bytes type input is used as private key data for authentication.
        :type pkey: str or bytes
        :param cert_file: Public key signed certificate file to use for
          authentication. The corresponding private key must also be provided
          via ``pkey`` parameter.
          For example ``pkey='id_rsa',cert_file='id_rsa-cert.pub'`` for RSA
          signed certificate.
          Path must be absolute or relative to user home directory.
        :type cert_file: str
        :param num_retries: (Optional) Number of connection and authentication
          attempts before the client gives up. Defaults to 3.
        :type num_retries: int
        :param retry_delay: Number of seconds to wait between retries. Defaults
          to :py:class:`pssh.constants.RETRY_DELAY`
        :type retry_delay: int
        :param timeout: (Optional) If provided, all commands will timeout after
          <timeout> number of seconds.
        :type timeout: int
        :param allow_agent: (Optional) set to False to disable connecting to
          the system's SSH agent. Currently unused.
        :type allow_agent: bool
        :param identity_auth: (Optional) set to False to disable attempting to
          authenticate with default identity files from
          `pssh.clients.base_ssh_client.BaseSSHClient.IDENTITIES`
        :type identity_auth: bool
        :param gssapi_server_identity: Enable GSS-API authentication.
          Uses GSS-MIC key exchange. Enabled if either gssapi_server_identity or
          gssapi_client_identity are provided.
        :type gssapi_auth: bool
        :type gssapi_server_identity: str
        :param gssapi_server_identity: Set GSSAPI server identity.
        :type gssapi_server_identity: str
        :param gssapi_client_identity: Set GSSAPI client identity.
        :type gssapi_client_identity: str
        :param gssapi_delegate_credentials: Enable/disable server credentials
          delegation.
        :type gssapi_delegate_credentials: bool
        :param ipv6_only: Choose IPv6 addresses only if multiple are available
          for the host or raise NoIPv6AddressFoundError otherwise. Note this will
          disable connecting to an IPv4 address if an IP address is provided instead.
        :type ipv6_only: bool

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        self.cert_file = _validate_pkey_path(cert_file)
        self.gssapi_auth = gssapi_auth
        self.gssapi_server_identity = gssapi_server_identity
        self.gssapi_client_identity = gssapi_client_identity
        self.gssapi_delegate_credentials = gssapi_delegate_credentials
        super(SSHClient, self).__init__(
            host, user=user, password=password, port=port, pkey=pkey,
            num_retries=num_retries, retry_delay=retry_delay,
            allow_agent=allow_agent,
            _auth_thread_pool=_auth_thread_pool,
            timeout=timeout,
            identity_auth=identity_auth,
            ipv6_only=ipv6_only,
        )

    def disconnect(self):
        """Close socket if needed."""
        if self.sock is not None and not self.sock.closed:
            self.sock.close()

    def _agent_auth(self):
        self.session.userauth_agent(self.user)

    def _keepalive(self):
        pass

    def _init_session(self, retries=1):
        logger.debug("Starting new session for %s@%s:%s",
                     self.user, self.host, self.port)
        self.session = Session()
        self.session.options_set(options.USER, self.user)
        self.session.options_set(options.HOST, self.host)
        self.session.options_set_port(self.port)
        if self.gssapi_server_identity:
            self.session.options_set(
                options.GSSAPI_SERVER_IDENTITY, self.gssapi_server_identity)
        if self.gssapi_client_identity:
            self.session.options_set(
                options.GSSAPI_CLIENT_IDENTITY, self.gssapi_client_identity)
        if self.gssapi_client_identity or self.gssapi_server_identity:
            self.session.options_set_gssapi_delegate_credentials(
                self.gssapi_delegate_credentials)
        logger.debug("Session started, connecting with existing socket")
        try:
            self.session.set_socket(self.sock)
            self._session_connect()
        except Exception as ex:
            if retries < self.num_retries:
                return self._connect_init_session_retry(retries=retries+1)
            msg = "Error connecting to host %s:%s - %s"
            logger.error(msg, self.host, self.port, ex)
            raise ex

    def _session_connect(self):
        self.session.connect()

    def auth(self):
        if self.gssapi_auth or (self.gssapi_server_identity or self.gssapi_client_identity):
            try:
                return self.session.userauth_gssapi()
            except Exception as ex:
                logger.error(
                    "GSSAPI authentication with server id %s and client id %s failed - %s",
                    self.gssapi_server_identity, self.gssapi_client_identity, ex)
        return super(SSHClient, self).auth()

    def _password_auth(self):
        self.session.userauth_password(self.user, self.password)

    def _pkey_file_auth(self, pkey_file, password=None):
        pkey = import_privkey_file(pkey_file, passphrase=password if password is not None else '')
        return self._pkey_obj_auth(pkey)

    def _pkey_obj_auth(self, pkey):
        if self.cert_file is not None:
            logger.debug("Certificate file set - trying certificate authentication")
            self._import_cert_file(pkey)
        self.session.userauth_publickey(pkey)

    def _pkey_from_memory(self, pkey_data):
        _pkey = import_privkey_base64(
            pkey_data,
            passphrase=self.password if self.password is not None else b'')
        return self._pkey_obj_auth(_pkey)

    def _import_cert_file(self, pkey):
        cert_key = import_cert_file(self.cert_file)
        self.session.userauth_try_publickey(cert_key)
        copy_cert_to_privkey(cert_key, pkey)
        logger.debug("Imported certificate file %s for pkey %s", self.cert_file, self.pkey)

    def _shell(self, channel):
        return self._eagain(channel.request_shell)

    def _open_session(self):
        channel = self.session.channel_new()
        channel.set_blocking(0)
        self._eagain(channel.open_session)
        return channel

    def open_session(self):
        """Open new channel from session."""
        logger.debug("Opening new channel on %s", self.host)
        try:
            channel = self._open_session()
        except Exception as ex:
            raise SessionError(ex)
        return channel

    def _make_output_readers(self, channel, stdout_buffer, stderr_buffer):
        _stdout_reader = spawn(
            self._read_output_to_buffer, channel, stdout_buffer)
        _stderr_reader = spawn(
            self._read_output_to_buffer, channel, stderr_buffer, is_stderr=True)
        return _stdout_reader, _stderr_reader

    def execute(self, cmd, use_pty=False, channel=None):
        """Execute command on remote host.

        :param cmd: The command string to execute.
        :type cmd: str
        :param use_pty: Whether or not to request a PTY on the channel executing
          command.
        :type use_pty: bool
        :param channel: Channel to use. New channel is created if not provided.
        :type channel: :py:class:`ssh.channel.Channel`"""
        channel = self.open_session() if not channel else channel
        if use_pty:
            self._eagain(channel.request_pty, timeout=self.timeout)
        logger.debug("Executing command '%s'", cmd)
        self._eagain(channel.request_exec, cmd, timeout=self.timeout)
        return channel

    def _read_output_to_buffer(self, channel, _buffer, is_stderr=False):
        while True:
            self.poll(timeout=self.timeout)
            try:
                size, data = channel.read_nonblocking(is_stderr=is_stderr)
            except EOF:
                _buffer.eof.set()
                sleep(.1)
                return
            if size > 0:
                _buffer.write(data)
            else:
                # Yield event loop to other greenlets if we have no data to
                # send back, meaning the generator does not yield and can there
                # for block other generators/greenlets from running.
                sleep(.1)

    def wait_finished(self, host_output, timeout=None):
        """Wait for EOF from channel and close channel.

        Used to wait for remote command completion and be able to gather
        exit code.

        :param host_output: Host output of command to wait for.
        :type host_output: :py:class:`pssh.output.HostOutput`
        :param timeout: Timeout value in seconds - defaults to no timeout.
        :type timeout: float

        :raises: :py:class:`pssh.exceptions.Timeout` after <timeout> seconds if
          timeout set.
        """
        if not isinstance(host_output, HostOutput):
            raise ValueError("%s is not a HostOutput object" % (host_output,))
        channel = host_output.channel
        if channel is None:
            return
        logger.debug("Sending EOF on channel %s", channel)
        self._eagain(channel.send_eof, timeout=self.timeout)
        logger.debug("Waiting for readers, timeout %s", timeout)
        with GTimeout(seconds=timeout, exception=Timeout):
            joinall((host_output.buffers.stdout.reader, host_output.buffers.stderr.reader))
        logger.debug("Readers finished, closing channel")
        self.close_channel(channel)

    def finished(self, channel):
        """Checks if remote command has finished - has server sent client
        EOF.

        :rtype: bool
        """
        if channel is None:
            return
        return channel.is_eof()

    def get_exit_status(self, channel):
        """Get exit status code for channel or ``None`` if not ready.

        :param channel: The channel to get status from.
        :type channel: :py:mod:`ssh.channel.Channel`
        :rtype: int or ``None``
        """
        if not channel.is_eof():
            return
        return channel.get_exit_status()

    def close_channel(self, channel):
        """Close channel.

        :param channel: The channel to close.
        :type channel: :py:class:`ssh.channel.Channel`
        """
        logger.debug("Closing channel")
        self._eagain(channel.close, timeout=self.timeout)

    def poll(self, timeout=None):
        """ssh-python based co-operative gevent poll on session socket."""
        self._poll_errcodes(
            self.session.get_poll_flags,
            SSH_READ_PENDING,
            SSH_WRITE_PENDING,
            timeout=timeout,
        )

    def _eagain(self, func, *args, **kwargs):
        """Run function given and handle EAGAIN for an ssh-python session"""
        return self._eagain_errcode(func, SSH_AGAIN, *args, **kwargs)

    def _eagain_write(self, write_func, data, timeout=None):
        return self._eagain_write_errcode(write_func, data, SSH_AGAIN, timeout=timeout)
