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
from warnings import warn

from gevent import sleep, socket, get_hub, spawn
from gevent.hub import Hub
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh2.exceptions import SFTPHandleError, SFTPProtocolError, \
    Timeout as SSH2Timeout
from ssh2.session import Session
from ssh2.sftp import LIBSSH2_FXF_READ, LIBSSH2_FXF_CREAT, LIBSSH2_FXF_WRITE, \
    LIBSSH2_FXF_TRUNC, LIBSSH2_SFTP_S_IRUSR, LIBSSH2_SFTP_S_IRGRP, \
    LIBSSH2_SFTP_S_IWUSR, LIBSSH2_SFTP_S_IXUSR, LIBSSH2_SFTP_S_IROTH, \
    LIBSSH2_SFTP_S_IXGRP, LIBSSH2_SFTP_S_IXOTH

from ...exceptions import UnknownHostException, AuthenticationException, \
     ConnectionErrorException, SessionError, SFTPError, SFTPIOError, Timeout, \
     SCPError
from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from ...native._ssh2 import wait_select, eagain_write, _read_output
from .common import _validate_pkey_path


Hub.NOT_ERROR = (Exception,)
host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger(__name__)
THREAD_POOL = get_hub().threadpool


class SSHClient(object):
    """ssh2-python (libssh2) based non-blocking SSH client."""

    IDENTITIES = (
        os.path.expanduser('~/.ssh/id_rsa'),
        os.path.expanduser('~/.ssh/id_dsa'),
        os.path.expanduser('~/.ssh/identity'),
        os.path.expanduser('~/.ssh/id_ecdsa'),
    )

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 forward_ssh_agent=False,
                 proxy_host=None,
                 _auth_thread_pool=True, keepalive_seconds=60):
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
        :param forward_ssh_agent: (Optional) Turn on SSH agent forwarding -
          equivalent to `ssh -A` from the `ssh` command line utility.
          Defaults to True if not set.
        :type forward_ssh_agent: bool
        :param proxy_host: Connection to host is via provided proxy host
          and client should use self.proxy_host for connection attempts.
        :type proxy_host: str
        :param keepalive_seconds: Interval of keep alive messages being sent to
          server. Set to ``0`` or ``False`` to disable.

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
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
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.allow_agent = allow_agent
        self.forward_ssh_agent = forward_ssh_agent
        self._forward_requested = False
        self.session = None
        self.keepalive_seconds = keepalive_seconds
        self._keepalive_greenlet = None
        self._host = proxy_host if proxy_host else host
        self.pkey = _validate_pkey_path(pkey, self.host)
        self._connect(self._host, self.port)
        if _auth_thread_pool:
            THREAD_POOL.apply(self._init)
        else:
            self._init()

    def disconnect(self):
        """Disconnect session, close socket if needed."""
        logger.debug("Disconnecting client for host %s", self.host)
        if self.session is not None:
            try:
                self._eagain(self.session.disconnect)
            except Exception:
                pass
        if self.sock is not None and not self.sock.closed:
            self.sock.close()
            logger.debug("Client socket closed for host %s", self.host)

    def __del__(self):
        self.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()

    def spawn_send_keepalive(self):
        """Spawns a new greenlet that sends keep alive messages every
        self.keepalive_seconds"""
        return spawn(self._send_keepalive)

    def _send_keepalive(self):
        while True:
            sleep(self._eagain(self.session.keepalive_send))

    def configure_keepalive(self):
        self.session.keepalive_config(False, self.keepalive_seconds)

    def _connect_init_retry(self, retries):
        retries += 1
        self.session = None
        if not self.sock.closed:
            self.sock.close()
        sleep(self.retry_delay)
        self._connect(self._host, self.port, retries=retries)
        return self._init(retries=retries)

    def _init(self, retries=1):
        self.session = Session()
        if self.timeout:
            # libssh2 timeout is in ms
            self.session.set_timeout(self.timeout * 1000)
        try:
            self.session.handshake(self.sock)
        except Exception as ex:
            while retries < self.num_retries:
                return self._connect_init_retry(retries)
            msg = "Error connecting to host %s:%s - %s"
            logger.error(msg, self.host, self.port, ex)
            if isinstance(ex, SSH2Timeout):
                raise Timeout(msg, self.host, self.port, ex)
            ex.host = self.host
            ex.port = self.port
            raise
        try:
            self.auth()
        except Exception as ex:
            while retries < self.num_retries:
                return self._connect_init_retry(retries)
            msg = "Authentication error while connecting to %s:%s - %s"
            raise AuthenticationException(msg, self.host, self.port, ex)
        self.session.set_blocking(0)
        if self.keepalive_seconds:
            self.configure_keepalive()
            self._keepalive_greenlet = self.spawn_send_keepalive()

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

    def _pkey_auth(self):
        self.session.userauth_publickey_fromfile(
            self.user,
            self.pkey,
            passphrase=self.password if self.password is not None else '')

    def _identity_auth(self):
        passphrase = self.password if self.password is not None else ''
        for identity_file in self.IDENTITIES:
            if not os.path.isfile(identity_file):
                continue
            logger.debug(
                "Trying to authenticate with identity file %s",
                identity_file)
            try:
                self.session.userauth_publickey_fromfile(
                    self.user,
                    identity_file,
                    passphrase=passphrase)
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
                "Proceeding with private key file authentication")
            return self._pkey_auth()
        if self.allow_agent:
            try:
                self.session.agent_auth(self.user)
            except Exception as ex:
                logger.debug("Agent auth failed with %s, "
                             "continuing with other authentication methods",
                             ex)
            else:
                logger.debug("Authentication with SSH Agent succeeded")
                return
        try:
            self._identity_auth()
        except AuthenticationException:
            if self.password is None:
                raise
            logger.debug("Private key auth failed, trying password")
            self._password_auth()

    def _password_auth(self):
        try:
            self.session.userauth_password(self.user, self.password)
        except Exception:
            raise AuthenticationException("Password authentication failed")

    def open_session(self):
        """Open new channel from session"""
        try:
            chan = self.session.open_session()
        except Exception as ex:
            raise SessionError(ex)
        while chan == LIBSSH2_ERROR_EAGAIN:
            wait_select(self.session)
            try:
                chan = self.session.open_session()
            except Exception as ex:
                raise SessionError(ex)
        # Multiple forward requests result in ChannelRequestDenied
        # errors, flag is used to avoid this.
        if self.forward_ssh_agent and not self._forward_requested:
            if not hasattr(chan, 'request_auth_agent'):
                warn("Requested SSH Agent forwarding but libssh2 version used "
                     "does not support it - ignoring")
                return chan
            self._eagain(chan.request_auth_agent)
            self._forward_requested = True
        return chan

    def execute(self, cmd, use_pty=False, channel=None):
        """Execute command on remote server.

        :param cmd: Command to execute.
        :type cmd: str
        :param use_pty: Whether or not to obtain a PTY on the channel.
        :type use_pty: bool
        :param channel: Use provided channel for execute rather than creating
          a new one.
        :type channel: :py:class:`ssh2.channel.Channel`
        """
        channel = self.open_session() if channel is None else channel
        if use_pty:
            self._eagain(channel.pty)
        logger.debug("Executing command '%s'" % cmd)
        self._eagain(channel.execute, cmd)
        return channel

    def read_stderr(self, channel, timeout=None):
        """Read standard error buffer from channel.

        :param channel: Channel to read output from.
        :type channel: :py:class:`ssh2.channel.Channel`
        """
        return _read_output(self.session, channel.read_stderr, timeout=timeout)

    def read_output(self, channel, timeout=None):
        """Read standard output buffer from channel.

        :param channel: Channel to read output from.
        :type channel: :py:class:`ssh2.channel.Channel`
        """
        return _read_output(self.session, channel.read, timeout=timeout)

    def _select_timeout(self, func, timeout):
        ret = func()
        while ret == LIBSSH2_ERROR_EAGAIN:
            wait_select(self.session, timeout=timeout)
            ret = func()
            if ret == LIBSSH2_ERROR_EAGAIN and timeout is not None:
                raise Timeout

    def wait_finished(self, channel, timeout=None):
        """Wait for EOF from channel and close channel.

        Used to wait for remote command completion and be able to gather
        exit code.

        :param channel: The channel to use.
        :type channel: :py:class:`ssh2.channel.Channel`
        """
        if channel is None:
            return
        # If .eof() returns EAGAIN after a select with a timeout, it means
        # it reached timeout without EOF and _select_timeout will raise
        # timeout exception causing the channel to appropriately
        # not be closed as the command is still running.
        self._select_timeout(channel.wait_eof, timeout)
        # Close channel to indicate no more commands will be sent over it
        self.close_channel(channel)

    def close_channel(self, channel):
        logger.debug("Closing channel")
        self._eagain(channel.close)

    def _eagain(self, func, *args, **kwargs):
        ret = func(*args, **kwargs)
        while ret == LIBSSH2_ERROR_EAGAIN:
            wait_select(self.session)
            ret = func(*args, **kwargs)
        return ret

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
                    encoding='utf-8', timeout=None):
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

        :rtype: (channel, host, stdout, stderr, stdin) tuple.
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
        channel = self.execute(_command, use_pty=use_pty)
        return channel, self.host, \
            self.read_output_buffer(
                self.read_output(channel, timeout=timeout),
                encoding=encoding), \
            self.read_output_buffer(
                self.read_stderr(channel, timeout=timeout), encoding=encoding,
                prefix='\t[err]'), channel

    def _make_sftp(self):
        """Make SFTP client from open transport"""
        try:
            sftp = self.session.sftp_init()
        except Exception as ex:
            raise SFTPError(ex)
        while sftp == LIBSSH2_ERROR_EAGAIN:
            wait_select(self.session)
            try:
                sftp = self.session.sftp_init()
            except Exception as ex:
                raise SFTPError(ex)
        return sftp

    def _mkdir(self, sftp, directory):
        """Make directory via SFTP channel

        :param sftp: SFTP client object
        :type sftp: :py:class:`ssh2.sftp.SFTP`
        :param directory: Remote directory to create
        :type directory: str

        :raises: :py:class:`pssh.exceptions.SFTPIOError` on SFTP IO errors
        """
        mode = LIBSSH2_SFTP_S_IRUSR | \
            LIBSSH2_SFTP_S_IWUSR | \
            LIBSSH2_SFTP_S_IXUSR | \
            LIBSSH2_SFTP_S_IRGRP | \
            LIBSSH2_SFTP_S_IROTH | \
            LIBSSH2_SFTP_S_IXGRP | \
            LIBSSH2_SFTP_S_IXOTH
        try:
            self._eagain(sftp.mkdir, directory, mode)
        except SFTPProtocolError as error:
            msg = "Error occured creating directory %s on host %s - %s"
            logger.error(msg, directory, self.host, error)
            raise SFTPIOError(msg, directory, self.host, error)
        logger.debug("Created remote directory %s", directory)

    def copy_file(self, local_file, remote_file, recurse=False,
                  sftp=None, _dir=None):
        """Copy local file to host via SFTP.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool

        :raises: :py:class:`ValueError` when a directory is supplied to
          ``local_file`` and ``recurse`` is not set
        :raises: :py:class:`pss.exceptions.SFTPError` on SFTP initialisation
          errors
        :raises: :py:class:`pssh.exceptions.SFTPIOError` on I/O errors writing
          via SFTP
        :raises: :py:class:`IOError` on local file IO errors
        :raises: :py:class:`OSError` on local OS errors like permission denied
        """
        sftp = self._make_sftp() if sftp is None else sftp
        if os.path.isdir(local_file) and recurse:
            return self._copy_dir(local_file, remote_file, sftp)
        elif os.path.isdir(local_file) and not recurse:
            raise ValueError("Recurse must be true if local_file is a "
                             "directory.")
        destination = self._remote_paths_split(remote_file)
        if destination is not None:
            try:
                self._eagain(sftp.stat, destination)
            except (SFTPHandleError, SFTPProtocolError):
                self.mkdir(sftp, destination)
        self.sftp_put(sftp, local_file, remote_file)
        logger.info("Copied local file %s to remote destination %s:%s",
                    local_file, self.host, remote_file)

    def _sftp_put(self, remote_fh, local_file):
        with open(local_file, 'rb', 2097152) as local_fh:
            for data in local_fh:
                eagain_write(remote_fh.write, data, self.session)

    def sftp_put(self, sftp, local_file, remote_file):
        mode = LIBSSH2_SFTP_S_IRUSR | \
               LIBSSH2_SFTP_S_IWUSR | \
               LIBSSH2_SFTP_S_IRGRP | \
               LIBSSH2_SFTP_S_IROTH
        f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE | LIBSSH2_FXF_TRUNC
        with self._sftp_openfh(
                sftp.open, remote_file, f_flags, mode) as remote_fh:
            try:
                self._sftp_put(remote_fh, local_file)
                # THREAD_POOL.apply(
                #     sftp_put, args=(self.session, remote_fh, local_file))
            except SFTPProtocolError as ex:
                msg = "Error writing to remote file %s - %s"
                logger.error(msg, remote_file, ex)
                raise SFTPIOError(msg, remote_file, ex)

    def mkdir(self, sftp, directory, _parent_path=None):
        """Make directory via SFTP channel.

        Parent paths in the directory are created if they do not exist.

        :param sftp: SFTP client object
        :type sftp: :py:class:`paramiko.sftp_client.SFTPClient`
        :param directory: Remote directory to create
        :type directory: str

        Catches and logs at error level remote IOErrors on creating directory.
        """
        try:
            _dir, sub_dirs = directory.split('/', 1)
        except ValueError:
            _dir = directory.split('/', 1)[0]
            sub_dirs = None
        if not _dir and directory.startswith('/'):
            try:
                _dir, sub_dirs = sub_dirs.split(os.path.sep, 1)
            except ValueError:
                return True
        if _parent_path is not None:
            _dir = '/'.join((_parent_path, _dir))
        try:
            self._eagain(sftp.stat, _dir)
        except (SFTPHandleError, SFTPProtocolError) as ex:
            logger.debug("Stat for %s failed with %s", _dir, ex)
            self._mkdir(sftp, _dir)
        if sub_dirs is not None:
            if directory.startswith('/'):
                _dir = ''.join(('/', _dir))
            return self.mkdir(sftp, sub_dirs, _parent_path=_dir)

    def _copy_dir(self, local_dir, remote_dir, sftp):
        """Call copy_file on every file in the specified directory, copying
        them to the specified remote directory."""
        file_list = os.listdir(local_dir)
        for file_name in file_list:
            local_path = os.path.join(local_dir, file_name)
            remote_path = '/'.join([remote_dir, file_name])
            self.copy_file(local_path, remote_path, recurse=True,
                           sftp=sftp)

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         sftp=None, encoding='utf-8'):
        """Copy remote file to local host via SFTP.

        :param remote_file: Remote filepath to copy from
        :type remote_file: str
        :param local_file: Local filepath where file(s) will be copied to
        :type local_file: str
        :param recurse: Whether or not to recursively copy directories
        :type recurse: bool
        :param encoding: Encoding to use for file paths.
        :type encoding: str

        :raises: :py:class:`ValueError` when a directory is supplied to
          ``local_file`` and ``recurse`` is not set
        :raises: :py:class:`pss.exceptions.SFTPError` on SFTP initialisation
          errors
        :raises: :py:class:`pssh.exceptions.SFTPIOError` on I/O errors reading
          from SFTP
        :raises: :py:class:`IOError` on local file IO errors
        :raises: :py:class:`OSError` on local OS errors like permission denied
        """
        sftp = self._make_sftp() if sftp is None else sftp
        try:
            self._eagain(sftp.stat, remote_file)
        except (SFTPHandleError, SFTPProtocolError):
            msg = "Remote file or directory %s does not exist"
            logger.error(msg, remote_file)
            raise SFTPIOError(msg, remote_file)
        try:
            dir_h = self._sftp_openfh(sftp.opendir, remote_file)
        except SFTPError:
            pass
        else:
            if not recurse:
                raise ValueError("Recurse must be true if remote_file is a "
                                 "directory.")
            file_list = self._sftp_readdir(dir_h)
            return self._copy_remote_dir(file_list, remote_file,
                                         local_file, sftp,
                                         encoding=encoding)
        destination = os.path.join(os.path.sep, os.path.sep.join(
            [_dir for _dir in local_file.split('/')
             if _dir][:-1]))
        self._make_local_dir(destination)
        self.sftp_get(sftp, remote_file, local_file)
        logger.info("Copied local file %s from remote destination %s:%s",
                    local_file, self.host, remote_file)

    def scp_recv(self, remote_file, local_file, recurse=False, sftp=None,
                 encoding='utf-8'):
        """Copy remote file to local host via SCP.

        Note - Remote directory listings are gather via SFTP when
        ``recurse`` is enabled - SCP lacks directory list support.
        Enabling recursion therefore involves creating an extra SFTP channel
        and requires SFTP support on the server.

        :param remote_file: Remote filepath to copy from
        :type remote_file: str
        :param local_file: Local filepath where file(s) will be copied to
        :type local_file: str
        :param recurse: Whether or not to recursively copy directories
        :type recurse: bool
        :param encoding: Encoding to use for file paths when recursion is
          enabled.
        :type encoding: str

        :raises: :py:class:`pssh.exceptions.SCPError` when a directory is
          supplied to ``local_file`` and ``recurse`` is not set.
        :raises: :py:class:`pssh.exceptions.SCPError` on errors copying file.
        :raises: :py:class:`IOError` on local file IO errors.
        :raises: :py:class:`OSError` on local OS errors like permission denied.
        """
        sftp = self._make_sftp() if (sftp is None and recurse) else sftp
        if recurse:
            try:
                self._eagain(sftp.stat, remote_file)
            except (SFTPHandleError, SFTPProtocolError):
                msg = "Remote file or directory %s does not exist"
                logger.error(msg, remote_file)
                raise SCPError(msg, remote_file)
            try:
                dir_h = self._sftp_openfh(sftp.opendir, remote_file)
            except SFTPError:
                pass
            else:
                file_list = self._sftp_readdir(dir_h)
                return self._scp_recv_dir(file_list, remote_file,
                                          local_file, sftp,
                                          encoding=encoding)
        destination = os.path.join(os.path.sep, os.path.sep.join(
            [_dir for _dir in local_file.split('/')
             if _dir][:-1]))
        self._make_local_dir(destination)
        self._scp_recv(remote_file, local_file)
        logger.info("SCP local file %s from remote destination %s:%s",
                    local_file, self.host, remote_file)

    def _scp_recv(self, remote_file, local_file):
        try:
            (file_chan, fileinfo) = self._eagain(
                self.session.scp_recv2, remote_file)
        except Exception as ex:
            msg = "Error copying file %s from host %s - %s"
            logger.error(msg, remote_file, self.host, ex)
            raise SCPError(msg, remote_file, self.host, ex)
        local_fh = open(local_file, 'wb')
        try:
            total = 0
            size, data = file_chan.read(size=fileinfo.st_size)
            while size == LIBSSH2_ERROR_EAGAIN:
                wait_select(self.session)
                size, data = file_chan.read(size=fileinfo.st_size)
            total += size
            local_fh.write(data)
            while total < fileinfo.st_size:
                size, data = file_chan.read(size=fileinfo.st_size - total)
                while size == LIBSSH2_ERROR_EAGAIN:
                    wait_select(self.session)
                    continue
                total += size
                local_fh.write(data)
            if total != fileinfo.st_size:
                msg = "Error copying data from remote file %s on host %s. " \
                      "Copied %s out of %s total bytes"
                raise SCPError(msg, remote_file, self.host, total,
                               fileinfo.st_size)
        finally:
            local_fh.close()

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
        """Copy local file to host via SCP.

        Note - Directories are created via SFTP when ``recurse`` is enabled -
        SCP lacks directory create support. Enabling recursion therefore
        involves creating an extra SFTP channel and requires SFTP support on the
        server.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool

        :raises: :py:class:`ValueError` when a directory is supplied to
          ``local_file`` and ``recurse`` is not set
        :raises: :py:class:`pss.exceptions.SFTPError` on SFTP initialisation
          errors
        :raises: :py:class:`pssh.exceptions.SFTPIOError` on I/O errors writing
          via SFTP
        :raises: :py:class:`IOError` on local file IO errors
        :raises: :py:class:`OSError` on local OS errors like permission denied
        """
        if os.path.isdir(local_file) and recurse:
            sftp = self._make_sftp() if sftp is None else sftp
            return self._scp_send_dir(local_file, remote_file, sftp)
        elif os.path.isdir(local_file) and not recurse:
            raise ValueError("Recurse must be True if local_file is a "
                             "directory.")
        destination = self._remote_paths_split(remote_file)
        if destination is not None:
            sftp = self._make_sftp() if sftp is None else sftp
            try:
                self._eagain(sftp.stat, destination)
            except (SFTPHandleError, SFTPProtocolError):
                self.mkdir(sftp, destination)
        self._scp_send(local_file, remote_file)
        logger.info("SCP local file %s to remote destination %s:%s",
                    local_file, self.host, remote_file)

    def _scp_send(self, local_file, remote_file):
        fileinfo = os.stat(local_file)
        try:
            chan = self._eagain(
                self.session.scp_send64,
                remote_file, fileinfo.st_mode & 0o777, fileinfo.st_size,
                fileinfo.st_mtime, fileinfo.st_atime)
        except Exception as ex:
            msg = "Error opening remote file %s for writing on host %s - %s"
            logger.error(msg, remote_file, self.host, ex)
            raise SCPError(msg, remote_file, self.host, ex)
        try:
            with open(local_file, 'rb', 2097152) as local_fh:
                for data in local_fh:
                    eagain_write(chan.write, data, self.session)
        except Exception as ex:
            msg = "Error writing to remote file %s on host %s - %s"
            logger.error(msg, remote_file, self.host, ex)
            raise SCPError(msg, remote_file, self.host, ex)

    def _sftp_readdir(self, dir_h):
        for size, buf, attrs in dir_h.readdir():
            for line in buf.splitlines():
                yield line

    def _sftp_openfh(self, open_func, remote_file, *args):
        try:
            fh = open_func(remote_file, *args)
        except Exception as ex:
            raise SFTPError(ex)
        while fh == LIBSSH2_ERROR_EAGAIN:
            wait_select(self.session, timeout=0.1)
            try:
                fh = open_func(remote_file, *args)
            except Exception as ex:
                raise SFTPError(ex)
        return fh

    def _sftp_get(self, remote_fh, local_file):
        with open(local_file, 'wb') as local_fh:
            for size, data in remote_fh:
                if size == LIBSSH2_ERROR_EAGAIN:
                    wait_select(self.session)
                    continue
                local_fh.write(data)

    def sftp_get(self, sftp, remote_file, local_file):
        with self._sftp_openfh(
                sftp.open, remote_file,
                LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as remote_fh:
            try:
                self._sftp_get(remote_fh, local_file)
                # Running SFTP in a thread requires a new session
                # as session handles or any handles created by a session
                # cannot be used simultaneously in multiple threads.
                # THREAD_POOL.apply(
                #     sftp_get, args=(self.session, remote_fh, local_file))
            except SFTPProtocolError as ex:
                msg = "Error reading from remote file %s - %s"
                logger.error(msg, remote_file, ex)
                raise SFTPIOError(msg, remote_file, ex)

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
        return

    def get_exit_status(self, channel):
        if not channel.eof():
            return
        return channel.get_exit_status()
