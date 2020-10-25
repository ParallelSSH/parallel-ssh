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
try:
    from io import BytesIO
except ImportError:
    from cStringIO import StringIO as BytesIO

from gevent import sleep, spawn, Timeout as GTimeout, joinall
from gevent.select import POLLIN, POLLOUT
from ssh import options
from ssh.session import Session, SSH_READ_PENDING, SSH_WRITE_PENDING
from ssh.key import import_privkey_file, import_cert_file, copy_cert_to_privkey
from ssh.exceptions import EOF
from ssh.error_codes import SSH_AGAIN

from ..base.single import BaseSSHClient
from ...exceptions import AuthenticationError, SessionError, Timeout
from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from ..common import _validate_pkey_path


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
        :type pkey: str
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

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        self.cert_file = _validate_pkey_path(cert_file, host)
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
            identity_auth=identity_auth)
        self._stdout_buffer = BytesIO()
        self._stderr_buffer = BytesIO()
        self._stdout_reader = None
        self._stderr_reader = None
        self._stdout_read = False
        self._stderr_read = False

    def disconnect(self):
        """Close socket if needed."""
        if self.sock is not None and not self.sock.closed:
            self.sock.close()

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
        self.session.set_socket(self.sock)
        logger.debug("Session started, connecting with existing socket")
        try:
            self.session.connect()
        except Exception as ex:
            if retries < self.num_retries:
                return self._connect_init_session_retry(retries=retries+1)
            msg = "Error connecting to host %s:%s - %s"
            logger.error(msg, self.host, self.port, ex)
            ex.host = self.host
            ex.port = self.port
            raise ex

    def auth(self):
        if self.pkey is not None:
            logger.debug(
                "Proceeding with private key file authentication")
            return self._pkey_auth(self.pkey, self.password)
        if self.allow_agent:
            try:
                self.session.userauth_agent(self.user)
            except Exception as ex:
                logger.debug(
                    "Agent auth failed with %s, "
                    "continuing with other authentication methods",
                    ex)
            else:
                logger.debug(
                    "Authentication with SSH Agent succeeded.")
                return
        if self.gssapi_auth or (self.gssapi_server_identity or self.gssapi_client_identity):
            try:
                self.session.userauth_gssapi()
            except Exception as ex:
                logger.error(
                    "GSSAPI authentication with server id %s and client id %s failed - %s",
                    self.gssapi_server_identity, self.gssapi_client_identity,
                    ex)
        if self.identity_auth:
            try:
                self._identity_auth()
            except AuthenticationError:
                if self.password is None:
                    raise
        logger.debug("Private key auth failed, trying password")
        self._password_auth()

    def _password_auth(self):
        if not self.password:
            raise AuthenticationError("All authentication methods failed")
        try:
            self.session.userauth_password(self.password)
        except Exception as ex:
            raise AuthenticationError("Password authentication failed - %s", ex)

    def _pkey_auth(self, pkey, password=None):
        pkey = import_privkey_file(pkey, passphrase=password)
        if self.cert_file is not None:
            logger.debug("Certificate file set - trying certificate authentication")
            self._import_cert_file(pkey)
        self.session.userauth_publickey(pkey)

    def _import_cert_file(self, pkey):
        cert_key = import_cert_file(self.cert_file)
        self.session.userauth_try_publickey(cert_key)
        copy_cert_to_privkey(cert_key, pkey)
        logger.debug("Imported certificate file %s for pkey %s", self.cert_file, self.pkey)

    def open_session(self):
        """Open new channel from session."""
        logger.debug("Opening new channel on %s", self.host)
        try:
            channel = self.session.channel_new()
            channel.set_blocking(0)
            while channel.open_session() == SSH_AGAIN:
                logger.debug(
                    "Channel open session blocked, waiting on socket..")
                self.poll(timeout=self.timeout)
                # Select on open session can dead lock without
                # yielding event loop
                sleep(.1)
        except Exception as ex:
            raise SessionError(ex)
        return channel

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
        self._eagain(channel.request_exec, cmd, timeout=self.timeout)
        self._stderr_read = False
        self._stdout_read = False
        self._stdout_buffer = BytesIO()
        self._stderr_buffer = BytesIO()
        self._stdout_reader = spawn(
            self._read_output_to_buffer, channel)
        self._stderr_reader = spawn(
            self._read_output_to_buffer, channel, is_stderr=True)
        self._stdout_reader.start()
        self._stderr_reader.start()
        return channel

    def read_stderr(self, channel, timeout=None):
        """Read standard error buffer from channel.
        Returns a generator of line by line output.

        :param channel: Channel to read output from.
        :type channel: :py:class:`ssh2.channel.Channel`
        :rtype: generator
        """
        _buffer_name = 'stderr'
        _buffer = self._stderr_buffer
        _flag = self._stderr_read
        _reader = self._stderr_reader
        return self._read_output(
            _buffer, _buffer_name, _flag, _reader, channel, timeout=timeout,
            is_stderr=True)

    def read_output(self, channel, timeout=None, is_stderr=False):
        """Read standard output buffer from channel.
        Returns a generator of line by line output.

        :param channel: Channel to read output from.
        :type channel: :py:class:`ssh2.channel.Channel`
        :rtype: generator
        """
        _buffer_name = 'stdout'
        _buffer = self._stdout_buffer
        _flag = self._stdout_read
        _reader = self._stdout_reader
        return self._read_output(
            _buffer, _buffer_name, _flag, _reader, channel, timeout=timeout)

    def _read_output(self, _buffer, _buffer_name, _flag, _reader, channel,
                     timeout=None, is_stderr=False):
        if _flag is True:
            logger.debug("Output for %s has already been read", _buffer_name)
            raise StopIteration
        logger.debug("Waiting for %s reader", _buffer_name)
        timeout = timeout if timeout else self.timeout
        try:
            _reader.get(timeout=timeout)
        except GTimeout as ex:
            raise Timeout(ex)
        if _buffer.getvalue() == '':
            logger.debug("Reader finished and output empty for %s",
                         _buffer_name)
            raise StopIteration
        logger.debug("Reading from %s buffer", _buffer_name)
        for line in _buffer.getvalue().splitlines():
            yield line
        if is_stderr:
            self._stderr_read = True
        else:
            self._stdout_read = True

    def _read_output_to_buffer(self, channel, is_stderr=False):
        _buffer_name = 'stderr' if is_stderr else 'stdout'
        _buffer = self._stderr_buffer if is_stderr else self._stdout_buffer
        logger.debug("Starting output generator on channel %s for %s",
                     channel, _buffer_name)
        while True:
            self.poll(timeout=self.timeout)
            try:
                size, data = channel.read_nonblocking(is_stderr=is_stderr)
            except EOF:
                logger.debug("Channel is at EOF trying to read %s - "
                             "reader exiting", _buffer_name)
                sleep(.1)
                return
            if size > 0:
                logger.debug("Writing %s bytes to %s buffer",
                             size, _buffer_name)
                _buffer.write(data)
            else:
                # Yield event loop to other greenlets if we have no data to
                # send back, meaning the generator does not yield and can there
                # for block other generators/greenlets from running.
                logger.debug("No data for %s, waiting", _buffer_name)
                sleep(.1)

    def wait_finished(self, channel, timeout=None):
        """Wait for EOF from channel and close channel.

        Used to wait for remote command completion and be able to gather
        exit code.

        :param channel: The channel to use.
        :type channel: :py:class:`ssh.channel.Channel`
        :param timeout: Timeout value in seconds - defaults to no timeout.
        :type timeout: float

        :raises: :py:class:`pssh.exceptions.Timeout` after <timeout> seconds if
          timeout given.
        """
        if channel is None:
            return
        logger.debug("Sending EOF on channel %s", channel)
        self._eagain(channel.send_eof, timeout=self.timeout)
        logger.debug("Waiting for readers, timeout %s", timeout)
        with GTimeout(seconds=timeout, exception=Timeout):
            joinall((self._stdout_reader, self._stderr_reader))
        logger.debug("Readers finished, closing channel")
        # Close channel
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
        """Get exit status from channel if ready else return `None`.

        :rtype: int or `None`
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
        """ssh-python based co-operative gevent select on session socket."""
        directions = self.session.get_poll_flags()
        if directions == 0:
            return
        events = 0
        if directions & SSH_READ_PENDING:
            events = POLLIN
        if directions & SSH_WRITE_PENDING:
            events |= POLLOUT
        self._poll_socket(events, timeout=timeout)

    def _eagain(self, func, *args, **kwargs):
        """Run function given and handle EAGAIN for an ssh-python session"""
        timeout = kwargs.pop('timeout', self.timeout)
        with GTimeout(seconds=timeout, exception=Timeout):
            ret = func(*args, **kwargs)
            while ret == SSH_AGAIN:
                self.poll(timeout=timeout)
                ret = func(*args, **kwargs)
            return ret
