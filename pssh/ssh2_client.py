# This file is part of parallel-ssh.

# Copyright (C) 2014-2017 Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""ssh2-python (libssh2) based SSH client package"""

import logging
import os
import pwd
from socket import gaierror as sock_gaierror, error as sock_error
from sys import version_info
from multiprocessing import cpu_count

from gevent import sleep, get_hub
from gevent.select import select
from gevent import socket
from ssh2.session import Session, LIBSSH2_SESSION_BLOCK_INBOUND, \
    LIBSSH2_SESSION_BLOCK_OUTBOUND
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh2.exceptions import AuthenticationError, AgentError, ChannelError

from .exceptions import UnknownHostException, AuthenticationException, \
     ConnectionErrorException, SSHException
from .constants import DEFAULT_RETRIES
from .native.ssh2 import open_session, wait_select

host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger(__name__)
LINESEP = os.linesep.encode('utf-8') if version_info > (2,) else os.linesep
THREAD_POOL = get_hub().threadpool


class SSHClient(object):
    """ssh2-python based SSH client"""

    IDENTITIES = [
        os.path.expanduser('~/.ssh/id_rsa'),
        os.path.expanduser('~/.ssh/id_dsa'),
        os.path.expanduser('~/.ssh/identity')
    ]

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None, forward_ssh_agent=None,
                 num_retries=DEFAULT_RETRIES, agent=None,
                 allow_agent=True, timeout=10,
                 proxy_host=None, proxy_port=22, proxy_user=None, 
                 proxy_password=None, proxy_pkey=None, channel_timeout=None,
                 _openssh_config_file=None):
        self.host = host
        self.user = user if user else pwd.getpwuid(os.geteuid()).pw_name
        self.password = password
        self.port = port if port else 22
        self.pkey = pkey
        self.num_retries = num_retries
        # self.forward_ssh_agent = forward_ssh_agent
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connect()
        THREAD_POOL.apply(self._init)

    def _init(self):
        self.session = Session()
        self.session.handshake(self.sock)
        self.auth()
        self.session.set_blocking(0)

    def _connect(self, retries=1):
        try:
            self.sock.connect((self.host, self.port))
        except sock_error as ex:
            logger.error("Error connecting to host '%s:%s' - retry %s/%s",
                         self.host, self.port, retries, self.num_retries)
            while retries < self.num_retries:
                sleep(5)
                return self._connect(retries=retries+1)
            error_type = ex.args[1] if len(ex.args) > 1 else ex.args[0]
            raise ConnectionErrorException(
                "Error connecting to host '%s:%s' - %s - retry %s/%s",
                self.host, self.port, str(error_type), retries,
                self.num_retries,)

    def _pkey_auth(self):
        pub_file = "{}.pub".format(self.pkey)
        logger.debug("Attempting authentication with public key %s for user %s",
                     pub_file, self.user)
        self._eagain(
            self.session.userauth_publickey_fromfile,
            self.user,
            pub_file,
            self.pkey,
            self.password if self.password is not None else '')

    def _identity_auth(self):
        for identity_file in self.IDENTITIES:
            if not os.path.isfile(identity_file):
                continue
            pub_file = "%s.pub" % (identity_file)
            logger.debug(
                "Trying to authenticate with identity file %s",
                identity_file)
            try:
                self._eagain(
                    self.session.userauth_publickey_fromfile,
                    self.user,
                    pub_file,
                    identity_file,
                    self.password if self.password is not None else '')
            except Exception:
                logger.debug("Authentication with identity file %s failed, "
                             "continuing with other identities",
                             identity_file)
                continue
            else:
                logger.debug("Authentication succeeded with identity file %s",
                             identity_file)
                return
        raise AuthenticationException("No authentication methods succeeded")

    def auth(self):
        if self.pkey is not None:
            logger.debug(
                "Proceeding with public key file authentication")
            return self._pkey_auth()
        try:
            self.session.agent_auth(self.user)
        except AuthenticationError as ex:
            logger.debug("Agent auth failed with %s, "
                         "continuing with other authentication methods",
                         ex)
        else:
            logger.debug("Authentication with SSH Agent succeeded")
            return
        try:
            self._identity_auth()
        except AuthenticationException:
            logger.debug("Public key auth failed, trying password")
            self._password_auth()

    def _password_auth(self):
        if not self.password:
            raise AuthenticationException(
                "No password provided - cannot authenticate via password")
        if self._eagain(self.session.userauth_password,
                        self.user, self.password) != 0:
            raise AuthenticationException(
                "Password authentication failed")

    def open_session(self):
        return open_session(self.sock, self.session)
        # return THREAD_POOL.apply(open_session, args=(self.sock, self.session))

    # def open_session(self):
    #     chan = self.session.open_session()
    #     while chan is None:
    #         wait_select(self.sock, self.session)
    #         chan = self.session.open_session()
    #     return chan

    def _run_with_retries(self, func, count=1, *args, **kwargs):
        while func(*args, **kwargs) == LIBSSH2_ERROR_EAGAIN:
            if count > self.num_retries:
                raise AuthenticationException(
                    "Error authenticating %s@%s", self.user, self.host,)
            count += 1

    def execute(self, cmd, use_pty=False, channel=None):
        logger.debug("Opening new channel for execute")
        channel = self.open_session() if channel is None else channel
        if use_pty:
            self._eagain(channel.pty)
        self._eagain(channel.execute, cmd)
        return channel

    def read_stderr(self, channel):
        return self._read_output(channel, channel.read_stderr)

    def read_output(self, channel):
        return self._read_output(channel, channel.read)

    def _read_output(self, channel, read_func):
        remainder = ""
        _pos = 0
        _size, _data = read_func()
        while _size == LIBSSH2_ERROR_EAGAIN:
            logger.debug("Waiting on socket read")
            wait_select(self.sock, self.session)
            _size, _data = read_func()
        while _size > 0:
            logger.debug("Got data size %s", _size)
            while _pos < _size:
                linesep = _data[:_size].find(LINESEP, _pos)
                if linesep > 0:
                    if len(remainder) > 0:
                        yield remainder + _data[_pos:linesep].strip()
                        remainder = ""
                    else:
                        yield _data[_pos:linesep].strip()
                        _pos = linesep + 1
                else:
                    remainder += _data[_pos:]
                    break
            _size, _data = read_func()
            _pos = 0
        self._eagain(channel.close)

    def wait_finished(self, channel):
        """Wait for EOF from channel, close channel and wait for
        close acknowledgement.

        :param channel: The channel to use
        :type channel: :py:class:`ssh2.channel.Channel`
        """
        if channel is None:
            return
        self._eagain(channel.wait_eof)
        self._eagain(channel.close)
        self._eagain(channel.wait_closed)

    def _eagain(self, func, *args, **kwargs):
        ret = func(*args, **kwargs)
        while ret == LIBSSH2_ERROR_EAGAIN:
            wait_select(self.sock, self.session)
            ret = func(*args, **kwargs)
        return ret

    def _wait_select(self):
        """
        Find out from libssh2 if its blocked on read or write and wait
        accordingly.

        Return immediately if libssh2 is not blocked.
        """
        directions = self.session.block_directions()
        if directions == 0:
            return
        readfds = [self.sock] \
            if (directions & LIBSSH2_SESSION_BLOCK_INBOUND) else ()
        writefds = [self.sock] \
            if (directions & LIBSSH2_SESSION_BLOCK_OUTBOUND) else ()
        select(readfds, writefds, [], 1)

    def read_output_buffer(self, output_buffer, prefix='',
                           callback=None,
                           callback_args=None,
                           encoding='utf-8'):
        """Read from output buffers and log to host_logger

        :param output_buffer: Iterator containing buffer
        :type output_buffer: iterator
        :param prefix: String to prefix log output to ``host_logger`` with
        :type prefix: str
        :param callback: Function to call back once buffer is depleted:
        :type callback: function
        :param callback_args: Arguments for call back function
        :type callback_args: tuple
        """
        for line in output_buffer:
            output = line.decode(encoding)
            host_logger.info("[%s]%s\t%s", self.host, prefix, output,)
            yield output
        if callback:
            callback(*callback_args)

    def run_command(self, command, sudo=False, user=None,
                    use_pty=False, use_shell=True, shell=None):
        channel = self.execute(command, use_pty=use_pty)
        return channel, self.host, \
            self.read_output_buffer(self.read_output(channel)), \
            self.read_output_buffer(self.read_stderr(channel)), \
            iter([])
