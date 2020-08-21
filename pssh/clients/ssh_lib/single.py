# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2018 Panos Kittenis.
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
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

from gevent import sleep, spawn, Timeout as GeventTimeout
from ssh import options
from ssh.session import Session
from ssh.key import import_privkey_file
from ssh.exceptions import EOF, FatalError
from ssh.error_codes import SSH_AGAIN

from ..base_ssh_client import BaseSSHClient
from ...exceptions import AuthenticationException, SessionError, Timeout
from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from ...native._ssh2 import wait_select_ssh as wait_select, eagain_ssh as eagain


logger = logging.getLogger(__name__)


class SSHClient(BaseSSHClient):
    """ssh-python based non-blocking client."""

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 _auth_thread_pool=False):
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
        :param num_retries: (Optional) Number of connection and authentication
          attempts before the client gives up. Defaults to 3.
        :type num_retries: int
        :param retry_delay: Number of seconds to wait between retries. Defaults
          to :py:class:`pssh.constants.RETRY_DELAY`
        :type retry_delay: int
        :param timeout: SSH session timeout setting in seconds. This controls
          timeout setting of authenticated SSH sessions.
        :type timeout: int
        :param allow_agent: (Optional) set to False to disable connecting to
          the system's SSH agent
        :type allow_agent: bool

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        super(SSHClient, self).__init__(
            host, user=user, password=password, port=port, pkey=pkey,
            num_retries=num_retries, retry_delay=retry_delay,
            allow_agent=allow_agent,
            _auth_thread_pool=_auth_thread_pool,
            timeout=timeout)
        self._stdout_buffer = BytesIO()
        self._stderr_buffer = BytesIO()
        self._stdout_reader = None
        self._stderr_reader = None
        self._stdout_read = False
        self._stderr_read = False

    def disconnect(self):
        """Close socket if needed."""
        if self.sock is not None and not self.sock.closed:
            logger.debug("Closing socket")
            self.sock.close()

    def _init(self, retries=1):
        logger.debug("Starting new session for %s@%s:%s",
                     self.user, self.host, self.port)
        self.session = Session()
        self.session.options_set(options.USER, self.user)
        self.session.options_set(options.HOST, self.host)
        self.session.options_set_port(self.port)
        self.session.set_socket(self.sock)
        logger.debug("Session started, connecting with existing socket")
        try:
            self.session.connect()
        except Exception as ex:
            while retries < self.num_retries:
                return self._connect_init_retry(retries)
            msg = "Error connecting to host %s:%s - %s"
            logger.error(msg, self.host, self.port, ex)
            raise
        try:
            self.auth()
        except Exception as ex:
            while retries < self.num_retries:
                return self._connect_init_retry(retries)
            msg = "Authentication error while connecting to %s:%s - %s"
            raise AuthenticationException(msg, self.host, self.port, ex)
        logger.debug("Authentication completed successfully - "
                     "setting session to non-blocking mode")
        self.session.set_blocking(0)

    def _password_auth(self):
        try:
            self.session.userauth_password(self.password)
        except Exception as ex:
            raise AuthenticationException(
                "Password authentication failed - %s", ex)

    def _pkey_auth(self, pkey, password=None):
        pkey = import_privkey_file(pkey, password)
        self.session.userauth_publickey(pkey)

    def open_session(self):
        logger.debug("Opening new channel on %s", self.host)
        try:
            channel = self.session.channel_new()
            while channel == SSH_AGAIN:
                wait_select(self.session, timeout=self.timeout)
                channel = self.session.channel_new()
            logger.debug("Channel %s created, opening session", channel)
            channel.set_blocking(0)
            while channel.open_session() == SSH_AGAIN:
                logger.debug(
                    "Channel open session blocked, waiting on socket..")
                wait_select(self.session, timeout=self.timeout)
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
            eagain(self.session, channel.request_pty, timeout=self.timeout)
        eagain(self.session, channel.request_exec, cmd, timeout=self.timeout)
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
        _buffer_name = 'stderr'
        _buffer = self._stderr_buffer
        _flag = self._stderr_read
        _reader = self._stderr_reader
        return self._read_output(
            _buffer, _buffer_name, _flag, _reader, channel, timeout=timeout,
            is_stderr=True)

    def read_output(self, channel, timeout=None, is_stderr=False):
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
        try:
            _reader.get(timeout=timeout)
        except GeventTimeout as ex:
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
            # try:
            #     if channel.poll():
            #         logger.debug("Socket blocked, waiting")
            #         logger.debug(
            #             "Socket no longer blocked - reading data from channel "
            #             "%s", channel)
            # except EOF:
            #     pass
            # except FatalError:
            #     channel.read()
            wait_select(self.session, timeout=self.timeout)
            try:
                size, data = channel.read_nonblocking(is_stderr=is_stderr)
            except EOF:
                logger.debug("Channel is at EOF trying to read %s - "
                             "reader exiting", _buffer_name)
                sleep()
                return
            except FatalError:
                wait_select(self.session, timeout=self.timeout)
                try:
                    size, data = channel.read_nonblocking(is_stderr=is_stderr)
                except EOF:
                    break
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
        """
        if channel is None:
            return
        logger.debug("Sending EOF on channel %s", channel)
        eagain(self.session, channel.send_eof,
               timeout=timeout if timeout else self.timeout)
        try:
            self._stdout_reader.get(timeout=timeout)
            self._stderr_reader.get(timeout=timeout)
        except GeventTimeout as ex:
            logger.debug("Timed out waiting for readers..")
            raise Timeout(ex)
        else:
            logger.debug("Readers finished, closing channel")
            # Close channel
            self.close_channel(channel)

    def finished(self, channel):
        if channel is None:
            return
        # import ipdb; ipdb.set_trace()
        return channel.is_eof()

    def get_exit_status(self, channel):
        if not channel.is_eof():
            return
        return channel.get_exit_status()

    def close_channel(self, channel):
        logger.debug("Closing channel")
        eagain(self.session, channel.close, timeout=self.timeout)
