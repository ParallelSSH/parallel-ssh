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

from gevent import sleep, socket, get_hub
from gevent.hub import Hub
from ssh import options
from ssh.session import Session, SSH_CLOSED, SSH_READ_PENDING, \
    SSH_WRITE_PENDING, SSH_CLOSED_ERROR
from ssh.channel import Channel
from ssh.key import SSHKey, import_pubkey_file, import_privkey_file
from ssh.exceptions import KeyImportError

from ..base_ssh_client import SSHClient
from ...exceptions import UnknownHostException, AuthenticationException, \
     ConnectionErrorException, SessionError, SFTPError, SFTPIOError, Timeout, \
     SCPError
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


Hub.NOT_ERROR = (Exception,)
host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger(__name__)
THREAD_POOL = get_hub().threadpool


class SSHClient(SSHClient):

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
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
            allow_agent=allow_agent, _auth_thread_pool=_auth_thread_pool)

    def disconnect(self):
        """Close socket if needed."""
        if self.sock is not None and not self.sock.closed:
            self.sock.close()

    def _init(self, retries=1):
        self.session = Session()
        self.session.options_set(options.USER, self.user)
        self.session.options_set(options.HOST, self.host)
        self.session.options_set_port(self.port)
        self.session.set_socket(self.sock)
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
        self.session.set_blocking(0)

    def _connect(self, host, port, retries=1):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.timeout:
            self.sock.settimeout(self.timeout)
        logger.debug("Connecting to %s:%s", host, port)
        try:
            self.sock.connect((host, port))
        except sock_gaierror as ex:
            logger.error("Could not resolve host '%s' - retry %s/%s",
                         host, retries, self.num_retries)
            while retries < self.num_retries:
                sleep(self.retry_delay)
                return self._connect(host, port, retries=retries+1)
            raise UnknownHostException("Unknown host %s - %s - retry %s/%s",
                                       host, str(ex.args[1]), retries,
                                       self.num_retries)
        except sock_error as ex:
            logger.error("Error connecting to host '%s:%s' - retry %s/%s",
                         host, port, retries, self.num_retries)
            while retries < self.num_retries:
                sleep(self.retry_delay)
                return self._connect(host, port, retries=retries+1)
            error_type = ex.args[1] if len(ex.args) > 1 else ex.args[0]
            raise ConnectionErrorException(
                "Error connecting to host '%s:%s' - %s - retry %s/%s",
                host, port, str(error_type), retries,
                self.num_retries,)

    def _password_auth(self):
        try:
            self.session.userauth_password(self.password)
        except Exception as ex:
            raise AuthenticationException("Password authentication failed - %s", ex)

    def _pkey_auth(self, pkey, password=None):
        pkey = import_privkey_file(pkey, password)
        self.session.userauth_publickey(pkey)

    def open_session(self):
        channel = self.session.channel_new()
        while not channel:
            self.wait_select(self.session)
            channel = self.session.channel_new()
        return channel
