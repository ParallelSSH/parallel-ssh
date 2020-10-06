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
import os
try:
    import pwd
except ImportError:
    WIN_PLATFORM = True
else:
    WIN_PLATFORM = False
from socket import gaierror as sock_gaierror, error as sock_error

from gevent import sleep, socket
from gevent.hub import Hub
from gevent.select import poll

from ..common import _validate_pkey_path
from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from ...exceptions import UnknownHostError, AuthenticationError, \
    ConnectionError
from ...output import HostOutput


Hub.NOT_ERROR = (Exception,)
host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger(__name__)


class BaseSSHClient(object):

    IDENTITIES = (
        os.path.expanduser('~/.ssh/id_rsa'),
        os.path.expanduser('~/.ssh/id_dsa'),
        os.path.expanduser('~/.ssh/identity'),
        os.path.expanduser('~/.ssh/id_ecdsa'),
        os.path.expanduser('~/.ssh/id_ed25519'),
    )

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 proxy_host=None,
                 _auth_thread_pool=True,
                 identity_auth=True):
        self._auth_thread_pool = _auth_thread_pool
        self.host = host
        self.user = user if user else None
        if self.user is None and not WIN_PLATFORM:
            self.user = pwd.getpwuid(os.geteuid()).pw_name
        elif self.user is None and WIN_PLATFORM:
            raise ValueError("Must provide user parameter on Windows")
        self.password = password
        self.port = port if port else 22
        self.num_retries = num_retries
        self.sock = None
        self.timeout = timeout if timeout else None
        self.retry_delay = retry_delay
        self.allow_agent = allow_agent
        self.session = None
        self._host = proxy_host if proxy_host else host
        self.pkey = _validate_pkey_path(pkey, self.host)
        self.identity_auth = identity_auth
        self._keepalive_greenlet = None
        self._init()

    def _init(self):
        self._connect(self._host, self.port)
        self._init_session()
        self._auth_retry()
        self._keepalive()
        logger.debug("Authentication completed successfully - "
                     "setting session to non-blocking mode")
        self.session.set_blocking(0)

    def _auth_retry(self, retries=1):
        try:
            self.auth()
        except Exception as ex:
            if retries < self.num_retries:
                sleep(self.retry_delay)
                return self._auth_retry(retries=retries+1)
            msg = "Authentication error while connecting to %s:%s - %s"
            raise AuthenticationError(msg, self.host, self.port, ex)

    def disconnect(self):
        raise NotImplementedError

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()

    def _connect_init_session_retry(self, retries):
        try:
            self.session.disconnect()
        except Exception:
            pass
        self.session = None
        if not self.sock.closed:
            try:
                self.sock.close()
            except Exception:
                pass
        sleep(self.retry_delay)
        self._connect(self._host, self.port, retries=retries)
        return self._init_session(retries=retries)

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
            if retries < self.num_retries:
                sleep(self.retry_delay)
                return self._connect(host, port, retries=retries+1)
            ex = UnknownHostError("Unknown host %s - %s - retry %s/%s",
                                  host, str(ex.args[1]), retries,
                                  self.num_retries)
            ex.host = host
            ex.port = port
            raise ex
        except sock_error as ex:
            logger.error("Error connecting to host '%s:%s' - retry %s/%s",
                         host, port, retries, self.num_retries)
            while retries < self.num_retries:
                sleep(self.retry_delay)
                return self._connect(host, port, retries=retries+1)
            error_type = ex.args[1] if len(ex.args) > 1 else ex.args[0]
            ex = ConnectionError(
                "Error connecting to host '%s:%s' - %s - retry %s/%s",
                host, port, str(error_type), retries,
                self.num_retries,)
            ex.host = host
            ex.port = port
            raise ex

    def _identity_auth(self):
        for identity_file in self.IDENTITIES:
            if not os.path.isfile(identity_file):
                continue
            logger.debug(
                "Trying to authenticate with identity file %s",
                identity_file)
            try:
                self._pkey_auth(identity_file, password=self.password)
            except Exception:
                logger.debug("Authentication with identity file %s failed, "
                             "continuing with other identities",
                             identity_file)
                continue
            else:
                logger.debug("Authentication succeeded with identity file %s",
                             identity_file)
                return
        raise AuthenticationError("No authentication methods succeeded")

    def _init_session(self, retries=1):
        raise NotImplementedError

    def _keepalive(self):
        raise NotImplementedError

    def auth(self):
        raise NotImplementedError

    def _password_auth(self):
        raise NotImplementedError

    def _pkey_auth(self, pkey, password=None):
        raise NotImplementedError

    def open_session(self):
        raise NotImplementedError

    def execute(self, cmd, use_pty=False, channel=None):
        raise NotImplementedError

    def read_stderr(self, channel, timeout=None):
        raise NotImplementedError

    def read_output(self, channel, timeout=None):
        raise NotImplementedError

    def _select_timeout(self, func, timeout):
        raise NotImplementedError

    def wait_finished(self, channel, timeout=None):
        raise NotImplementedError

    def close_channel(self, channel):
        raise NotImplementedError

    def get_exit_status(self, channel):
        if not channel.eof():
            return
        return channel.get_exit_status()

    def read_output_buffer(self, output_buffer, prefix=None,
                           callback=None,
                           callback_args=None,
                           encoding='utf-8'):
        """Read from output buffers and log to ``host_logger``.

        :param output_buffer: Iterator containing buffer
        :type output_buffer: iterator
        :param prefix: String to prefix log output to ``host_logger`` with
        :type prefix: str
        :param callback: Function to call back once buffer is depleted:
        :type callback: function
        :param callback_args: Arguments for call back function
        :type callback_args: tuple
        """
        prefix = '' if prefix is None else prefix
        for line in output_buffer:
            output = line.decode(encoding)
            host_logger.info("[%s]%s\t%s", self.host, prefix, output)
            yield output
        if callback:
            callback(*callback_args)

    def run_command(self, command, sudo=False, user=None,
                    use_pty=False, shell=None,
                    encoding='utf-8', timeout=None, read_timeout=None):
        """Run remote command.

        :param command: Command to run.
        :type command: str
        :param sudo: Run command via sudo as super-user.
        :type sudo: bool
        :param user: Run command as user via sudo
        :type user: str
        :param use_pty: Whether or not to obtain a PTY on the channel.
        :type use_pty: bool
        :param shell: (Optional) Override shell to use to run command with.
          Defaults to login user's defined shell. Use the shell's command
          syntax, eg `shell='bash -c'` or `shell='zsh -c'`.
        :type shell: str
        :param encoding: Encoding to use for output. Must be valid
          `Python codec <https://docs.python.org/2.7/library/codecs.html>`_
        :type encoding: str
        :param read_timeout: (Optional) Timeout in seconds for reading output.
        :type read_timeout: float

        :rtype: :py:class:`pssh.output.HostOutput`
        """
        # Fast path for no command substitution needed
        if not sudo and not user and not shell:
            _command = command
        else:
            _command = ''
            if sudo and not user:
                _command = 'sudo -S '
            elif user:
                _command = 'sudo -u %s -S ' % (user,)
            _shell = shell if shell else '$SHELL -c'
            _command += "%s '%s'" % (_shell, command,)
        _timeout = read_timeout if read_timeout else timeout
        channel = self.execute(_command, use_pty=use_pty)
        stdout = self.read_output_buffer(
            self.read_output(channel, timeout=_timeout),
            encoding=encoding)
        stderr = self.read_output_buffer(
                self.read_stderr(channel, timeout=_timeout), encoding=encoding,
                prefix='\t[err]')
        stdin = channel
        host_out = HostOutput(self.host, channel, stdout, stderr, stdin, self)
        return host_out

    def _eagain(self, func, *args, **kwargs):
        raise NotImplementedError

    def _make_sftp(self):
        raise NotImplementedError

    def _mkdir(self, sftp, directory):
        raise NotImplementedError

    def copy_file(self, local_file, remote_file, recurse=False,
                  sftp=None, _dir=None):
        raise NotImplementedError

    def _sftp_put(self, remote_fh, local_file):
        with open(local_file, 'rb') as local_fh:
            for data in local_fh:
                self._eagain(remote_fh.write, data)

    def sftp_put(self, sftp, local_file, remote_file):
        raise NotImplementedError

    def mkdir(self, sftp, directory, _parent_path=None):
        raise NotImplementedError

    def _copy_dir(self, local_dir, remote_dir, sftp):
        """Call copy_file on every file in the specified directory, copying
        them to the specified remote directory."""
        self.mkdir(sftp, remote_dir)
        file_list = os.listdir(local_dir)
        for file_name in file_list:
            local_path = os.path.join(local_dir, file_name)
            remote_path = '/'.join([remote_dir, file_name])
            self.copy_file(local_path, remote_path, recurse=True,
                           sftp=sftp)

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         sftp=None, encoding='utf-8'):
        raise NotImplementedError

    def scp_recv(self, remote_file, local_file, recurse=False, sftp=None,
                 encoding='utf-8'):
        raise NotImplementedError

    def _scp_recv(self, remote_file, local_file):
        raise NotImplementedError

    def _scp_send_dir(self, local_dir, remote_dir, sftp):
        file_list = os.listdir(local_dir)
        for file_name in file_list:
            local_path = os.path.join(local_dir, file_name)
            remote_path = '/'.join([remote_dir, file_name])
            self.scp_send(local_path, remote_path, recurse=True,
                          sftp=sftp)

    def _scp_recv_dir(self, file_list, remote_dir, local_dir, sftp,
                      encoding='utf-8'):
        for file_name in file_list:
            file_name = file_name.decode(encoding)
            if file_name in ('.', '..'):
                continue
            remote_path = os.path.join(remote_dir, file_name)
            local_path = os.path.join(local_dir, file_name)
            logger.debug("Attempting recursive copy from %s:%s to %s",
                         self.host, remote_path, local_path)
            self.scp_recv(remote_path, local_path, sftp=sftp,
                          recurse=True)

    def scp_send(self, local_file, remote_file, recurse=False, sftp=None):
        raise NotImplementedError

    def _scp_send(self, local_file, remote_file):
        raise NotImplementedError

    def _sftp_readdir(self, dir_h):
        for size, buf, attrs in dir_h.readdir():
            for line in buf.splitlines():
                yield line

    def _sftp_openfh(self, open_func, remote_file, *args):
        raise NotImplementedError

    def _sftp_get(self, remote_fh, local_file):
        raise NotImplementedError

    def sftp_get(self, sftp, remote_file, local_file):
        raise NotImplementedError

    def _copy_remote_dir(self, file_list, remote_dir, local_dir, sftp,
                         encoding='utf-8'):
        for file_name in file_list:
            file_name = file_name.decode(encoding)
            if file_name in ('.', '..'):
                continue
            remote_path = os.path.join(remote_dir, file_name)
            local_path = os.path.join(local_dir, file_name)
            self.copy_remote_file(remote_path, local_path, sftp=sftp,
                                  recurse=True)

    def _make_local_dir(self, dirpath):
        if os.path.exists(dirpath):
            return
        try:
            os.makedirs(dirpath)
        except OSError:
            logger.error("Unable to create local directory structure for "
                         "directory %s", dirpath)
            raise

    def _remote_paths_split(self, file_path):
        _sep = file_path.rfind('/')
        if _sep > 0:
            return file_path[:_sep]

    def poll(timeout=None):
        raise NotImplementedError

    def _poll_socket(self, events, timeout=None):
        if self.sock is None:
            return
        # gevent.select.poll converts seconds to miliseconds to match python socket
        # implementation
        timeout = timeout * 1000 if timeout is not None else 100
        poller = poll()
        poller.register(self.sock, eventmask=events)
        logger.debug("Polling socket with timeout %s", timeout)
        poller.poll(timeout=timeout)
