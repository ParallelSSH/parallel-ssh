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
import os
try:
    import pwd
except ImportError:
    WIN_PLATFORM = True
else:
    WIN_PLATFORM = False
from socket import gaierror as sock_gaierror, error as sock_error

from gevent import sleep, socket
from gevent.select import select
from ssh import options
from ssh.session import Session, SSH_CLOSED, SSH_READ_PENDING, \
    SSH_WRITE_PENDING, SSH_CLOSED_ERROR
from ssh.channel import Channel
from ssh.key import SSHKey, import_pubkey_file, import_privkey_file
from ssh.exceptions import KeyImportError, EOF
from ssh.error_codes import SSH_AGAIN

from ..base_ssh_client import BaseSSHClient
from ...exceptions import UnknownHostException, AuthenticationException, \
     ConnectionErrorException, SessionError, SFTPError, SFTPIOError, Timeout, \
     SCPError
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)


class SSHClient(BaseSSHClient):

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
            allow_agent=allow_agent, _auth_thread_pool=_auth_thread_pool,
            timeout=timeout)

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
            raise AuthenticationException("Password authentication failed - %s", ex)

    def _pkey_auth(self, pkey, password=None):
        pkey = import_privkey_file(pkey, password)
        self.session.userauth_publickey(pkey)

    def open_session(self):
        logger.debug("Opening new channel on %s", self.host)
        try:
            channel = self.session.channel_new()
            while channel == SSH_AGAIN:
                self.wait_select()
                channel = self.session.channel_new()
            logger.debug("Channel %s created, opening session", channel)
            channel.set_blocking(0)
            while channel.open_session() == SSH_AGAIN:
                logger.debug("Channel open session blocked, waiting on socket..")
                self.wait_select()
                # Select on open session can dead lock without
                # yielding event loop
                sleep(.1)
        except Exception as ex:
            raise SessionError(ex)
        return channel

    def execute(self, cmd, use_pty=False, channel=None):
        channel = self.open_session() if not channel else channel
        if use_pty:
            self.eagain(channel.request_pty, timeout=self.timeout)
        self.eagain(channel.request_exec, cmd, timeout=self.timeout)
        return channel

    def read_stderr(self, channel, timeout=None):
        return self.read_output(channel, timeout=timeout, is_stderr=True)

    def read_output(self, channel, timeout=None, is_stderr=False):
        logger.debug("Starting output generator on channel %s for %s",
                     channel, 'stderr' if is_stderr else 'stdout')
        while True:
            try:
                if channel.poll():
                    self.wait_select()
                    logger.debug(
                        "Socket no longer blocked - reading data from channel "
                        "%s", channel)
            except EOF:
                pass
            try:
                size, data = channel.read_nonblocking(is_stderr=is_stderr)
            except EOF:
                sleep()
                raise StopIteration
            if size > 0:
                yield data
            else:
                # Yield event loop to other greenlets if we have no data to
                # send back, meaning the generator does not yield and can there
                # for block other generators/greenlets from running.
                sleep(1)

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
        self.eagain(channel.send_eof, timeout=timeout)
        # import ipdb; ipdb.set_trace()
        for _ in self.read_output(channel, timeout=timeout):
            pass
        for _ in self.read_output(channel, timeout=timeout, is_stderr=True):
            pass
        # Close channel
        self.close_channel(channel)

    def _eagain(self, func, *args, **kwargs):
        self.wait_select()
        return func(*args, **kwargs)

    def eagain(self, func, *args, **kwargs):
        """Run function given EAGAIN"""
        timeout = kwargs.pop('timeout', self.timeout)
        ret = func(*args, **kwargs)
        while ret == SSH_AGAIN:
            self.wait_select(timeout=timeout)
            ret = func(*args, **kwargs)
            if ret == SSH_AGAIN and timeout is not None:
                raise Timeout
        sleep()
        return ret

    def wait_select(self, timeout=None):
        directions = self.session.get_poll_flags()
        if directions == 0:
            return 0
        readfds = (self.sock,) \
            if (directions & SSH_READ_PENDING) else ()
        writefds = (self.sock,) \
            if (directions & SSH_WRITE_PENDING) else ()
        select(readfds, writefds, (), timeout=timeout)
