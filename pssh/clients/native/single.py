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
from collections import deque
from warnings import warn

from gevent import sleep, spawn, get_hub
from gevent.lock import RLock
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh2.exceptions import SFTPHandleError, SFTPProtocolError, \
    Timeout as SSH2Timeout
from ssh2.session import Session, LIBSSH2_SESSION_BLOCK_INBOUND, LIBSSH2_SESSION_BLOCK_OUTBOUND
from ssh2.sftp import LIBSSH2_FXF_READ, LIBSSH2_FXF_CREAT, LIBSSH2_FXF_WRITE, \
    LIBSSH2_FXF_TRUNC, LIBSSH2_SFTP_S_IRUSR, LIBSSH2_SFTP_S_IRGRP, \
    LIBSSH2_SFTP_S_IWUSR, LIBSSH2_SFTP_S_IXUSR, LIBSSH2_SFTP_S_IROTH, \
    LIBSSH2_SFTP_S_IXGRP, LIBSSH2_SFTP_S_IXOTH

from .tunnel import FORWARDER
from ..base.single import BaseSSHClient
from ...output import HostOutput
from ...exceptions import SessionError, SFTPError, \
    SFTPIOError, Timeout, SCPError, ProxyError
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)
THREAD_POOL = get_hub().threadpool


class SSHClient(BaseSSHClient):
    """ssh2-python (libssh2) based non-blocking SSH client."""
    # 2MB buffer
    _BUF_SIZE = 2048 * 1024

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 forward_ssh_agent=False,
                 proxy_host=None,
                 proxy_port=None,
                 proxy_pkey=None,
                 proxy_user=None,
                 proxy_password=None,
                 _auth_thread_pool=True, keepalive_seconds=60,
                 identity_auth=True,
                 ipv6_only=False,
                 ):
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
        :param identity_auth: (Optional) set to False to disable attempting to
          authenticate with default identity files from
          `pssh.clients.base.single.BaseSSHClient.IDENTITIES`
        :type identity_auth: bool
        :param forward_ssh_agent: Unused - agent forwarding not implemented.
        :type forward_ssh_agent: bool
        :param proxy_host: Connect to target host via given proxy host.
        :type proxy_host: str
        :param proxy_port: Port to use for proxy connection. Defaults to self.port
        :type proxy_port: int
        :param keepalive_seconds: Interval of keep alive messages being sent to
          server. Set to ``0`` or ``False`` to disable.
        :type keepalive_seconds: int
        :param ipv6_only: Choose IPv6 addresses only if multiple are available
          for the host or raise NoIPv6AddressFoundError otherwise. Note this will
          disable connecting to an IPv4 address if an IP address is provided instead.
        :type ipv6_only: bool

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        self.forward_ssh_agent = forward_ssh_agent
        self._forward_requested = False
        self.keepalive_seconds = keepalive_seconds
        self._keepalive_greenlet = None
        self._proxy_client = None
        self.host = host
        self.port = port if port is not None else 22
        if proxy_host is not None:
            _port = port if proxy_port is None else proxy_port
            _pkey = pkey if proxy_pkey is None else proxy_pkey
            _user = user if proxy_user is None else proxy_user
            _password = password if proxy_password is None else proxy_password
            proxy_port = self._connect_proxy(
                proxy_host, _port, _pkey, user=_user, password=_password,
                num_retries=num_retries, retry_delay=retry_delay,
                allow_agent=allow_agent,
                timeout=timeout,
                keepalive_seconds=keepalive_seconds,
                identity_auth=identity_auth,
            )
            proxy_host = '127.0.0.1'
        self._chan_lock = RLock()
        super(SSHClient, self).__init__(
            host, user=user, password=password, port=port, pkey=pkey,
            num_retries=num_retries, retry_delay=retry_delay,
            allow_agent=allow_agent, _auth_thread_pool=_auth_thread_pool,
            timeout=timeout,
            proxy_host=proxy_host, proxy_port=proxy_port,
            identity_auth=identity_auth,
            ipv6_only=ipv6_only,
        )

    def _shell(self, channel):
        return self._eagain(channel.shell)

    def _connect_proxy(self, proxy_host, proxy_port, proxy_pkey,
                       user=None, password=None,
                       num_retries=DEFAULT_RETRIES,
                       retry_delay=RETRY_DELAY,
                       allow_agent=True, timeout=None,
                       forward_ssh_agent=False,
                       keepalive_seconds=60,
                       identity_auth=True):
        assert isinstance(self.port, int)
        try:
            self._proxy_client = SSHClient(
                proxy_host, port=proxy_port, pkey=proxy_pkey,
                num_retries=num_retries, user=user, password=password,
                retry_delay=retry_delay, allow_agent=allow_agent,
                timeout=timeout, forward_ssh_agent=forward_ssh_agent,
                identity_auth=identity_auth,
                keepalive_seconds=keepalive_seconds,
                _auth_thread_pool=False)
        except Exception as ex:
            msg = "Proxy authentication failed. " \
                  "Exception from tunnel client: %s"
            logger.error(msg, ex)
            raise ProxyError(msg, ex)
        if not FORWARDER.started.is_set():
            FORWARDER.start()
            FORWARDER.started.wait()
        FORWARDER.enqueue(self._proxy_client, self.host, self.port)
        proxy_local_port = FORWARDER.out_q.get()
        return proxy_local_port

    def disconnect(self):
        """Attempt to disconnect session.

        Any errors on calling disconnect are suppressed by this function.
        """
        self._keepalive_greenlet = None
        if self.session is not None:
            try:
                self._disconnect_eagain()
            except Exception:
                pass
            self.session = None
        if isinstance(self._proxy_client, SSHClient):
            # Don't disconnect proxy client here - let the TunnelServer do it at the time that
            # _wait_send_receive_lets ends. The cleanup_server call here triggers the TunnelServer
            # to stop.
            FORWARDER.cleanup_server(self._proxy_client)

            # I wanted to clean up all the sockets here to avoid a ResourceWarning from unittest,
            # but unfortunately closing this socket here causes a segfault, not sure why yet.
            # self.sock.close()
        else:
            self.sock.close()
        self.sock = None

    def spawn_send_keepalive(self):
        """Spawns a new greenlet that sends keep alive messages every
        self.keepalive_seconds"""
        return spawn(self._send_keepalive)

    def _send_keepalive(self):
        while True:
            sleep(self._eagain(self.session.keepalive_send))

    def configure_keepalive(self):
        self.session.keepalive_config(False, self.keepalive_seconds)

    def _init_session(self, retries=1):
        self.session = Session()
        if self.timeout:
            # libssh2 timeout is in ms
            self.session.set_timeout(self.timeout * 1000)
        try:
            if self._auth_thread_pool:
                THREAD_POOL.apply(self.session.handshake, (self.sock,))
            else:
                self.session.handshake(self.sock)
        except Exception as ex:
            if retries < self.num_retries:
                sleep(self.retry_delay)
                return self._connect_init_session_retry(retries=retries+1)
            msg = "Error connecting to host %s:%s - %s"
            logger.error(msg, self.host, self.port, ex)
            if isinstance(ex, SSH2Timeout):
                raise Timeout(msg, self.host, self.port, ex)
            raise

    def _keepalive(self):
        if self.keepalive_seconds:
            self.configure_keepalive()
            self._keepalive_greenlet = self.spawn_send_keepalive()

    def _agent_auth(self):
        self.session.agent_auth(self.user)

    def _pkey_file_auth(self, pkey_file, password=None):
        self.session.userauth_publickey_fromfile(
            self.user,
            pkey_file,
            passphrase=password if password is not None else b'')

    def _pkey_from_memory(self, pkey_data):
        self.session.userauth_publickey_frommemory(
            self.user,
            pkey_data,
            passphrase=self.password if self.password is not None else b'',
        )

    def _password_auth(self):
        self.session.userauth_password(self.user, self.password)

    def _open_session(self):
        chan = self._eagain(self.session.open_session)
        return chan

    def open_session(self):
        """Open new channel from session"""
        try:
            chan = self._open_session()
        except Exception as ex:
            raise SessionError(ex)
        if self.forward_ssh_agent and not self._forward_requested:
            if not hasattr(chan, 'request_auth_agent'):
                warn("Requested SSH Agent forwarding but libssh2 version used "
                     "does not support it - ignoring")
                return chan
            # self._eagain(chan.request_auth_agent)
            # self._forward_requested = True
        return chan

    def _make_output_readers(self, channel, stdout_buffer, stderr_buffer):
        _stdout_reader = spawn(
            self._read_output_to_buffer, channel.read, stdout_buffer)
        _stderr_reader = spawn(
            self._read_output_to_buffer, channel.read_stderr, stderr_buffer)
        return _stdout_reader, _stderr_reader

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
        logger.debug("Executing command '%s'", cmd)
        self._eagain(channel.execute, cmd)
        return channel

    def _read_output_to_buffer(self, read_func, _buffer):
        try:
            while True:
                with self._chan_lock:
                    size, data = read_func()
                while size == LIBSSH2_ERROR_EAGAIN:
                    self.poll()
                    with self._chan_lock:
                        size, data = read_func()
                if size <= 0:
                    break
                _buffer.write(data)
        finally:
            _buffer.eof.set()

    def wait_finished(self, host_output, timeout=None):
        """Wait for EOF from channel and close channel.

        Used to wait for remote command completion and be able to gather
        exit code.

        :param host_output: Host output of command to wait for.
        :type host_output: :py:class:`pssh.output.HostOutput`
        :param timeout: Timeout value in seconds - defaults to no timeout.
        :type timeout: float

        :raises: :py:class:`pssh.exceptions.Timeout` after <timeout> seconds if
          timeout given.
        """
        if not isinstance(host_output, HostOutput):
            raise ValueError("%s is not a HostOutput object" % (host_output,))
        channel = host_output.channel
        if channel is None:
            return
        self._eagain(channel.wait_eof, timeout=timeout)
        # Close channel to indicate no more commands will be sent over it
        self.close_channel(channel)

    def close_channel(self, channel):
        with self._chan_lock:
            logger.debug("Closing channel")
            self._eagain(channel.close)

    def _eagain(self, func, *args, **kwargs):
        return self._eagain_errcode(func, LIBSSH2_ERROR_EAGAIN, *args, **kwargs)

    def _make_sftp_eagain(self):
        return self._eagain(self.session.sftp_init)

    def _make_sftp(self):
        """Make SFTP client from open transport"""
        try:
            sftp = self._make_sftp_eagain()
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

    def copy_file(self, local_file, remote_file, recurse=False, sftp=None):
        """Copy local file to host via SFTP.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool
        :param sftp: SFTP channel to use instead of creating a
          new one.
        :type sftp: :py:class:`ssh2.sftp.SFTP`

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
        with open(local_file, 'rb', self._BUF_SIZE) as local_fh:
            data = local_fh.read(self._BUF_SIZE)
            while data:
                self.eagain_write(remote_fh.write, data)
                data = local_fh.read(self._BUF_SIZE)

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
            except SFTPProtocolError as ex:
                msg = "Error writing to remote file %s - %s"
                logger.error(msg, remote_file, ex)
                raise SFTPIOError(msg, remote_file, ex)

    def mkdir(self, sftp, directory):
        """Make directory via SFTP channel.

        Parent paths in the directory are created if they do not exist.

        :param sftp: SFTP client object
        :type sftp: :py:class:`ssh2.sftp.SFTP`
        :param directory: Remote directory to create
        :type directory: str

        Catches and logs at error level remote IOErrors on creating directory.
        """
        _paths_to_create = deque()
        for d in directory.split('/'):
            if not d:
                continue
            _paths_to_create.append(d)
        cwd = '' if directory.startswith('/') else '.'
        while _paths_to_create:
            cur_dir = _paths_to_create.popleft()
            cwd = '/'.join([cwd, cur_dir])
            try:
                self._eagain(sftp.stat, cwd)
            except (SFTPHandleError, SFTPProtocolError) as ex:
                logger.debug("Stat for %s failed with %s", cwd, ex)
                self._mkdir(sftp, cwd)

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
        :param sftp: SFTP channel to use instead of creating a
          new one.
        :type sftp: :py:class:`ssh2.sftp.SFTP`

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
            msg = "Remote file or directory %s on host %s does not exist"
            logger.error(msg, remote_file, self.host)
            raise SFTPIOError(msg, remote_file, self.host)
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

    def _scp_recv_recursive(self, remote_file, local_file, sftp, encoding='utf-8'):
        try:
            self._eagain(sftp.stat, remote_file)
        except (SFTPHandleError, SFTPProtocolError):
            msg = "Remote file or directory %s does not exist"
            logger.error(msg, remote_file)
            raise SCPError(msg, remote_file)
        try:
            dir_h = self._sftp_openfh(sftp.opendir, remote_file)
        except SFTPError:
            # remote_file is not a dir, scp file
            return self.scp_recv(remote_file, local_file, encoding=encoding)
        try:
            os.makedirs(local_file)
        except OSError:
            pass
        file_list = self._sftp_readdir(dir_h)
        return self._scp_recv_dir(file_list, remote_file,
                                  local_file, sftp,
                                  encoding=encoding)

    def scp_recv(self, remote_file, local_file, recurse=False, sftp=None,
                 encoding='utf-8'):
        """Copy remote file to local host via SCP.

        Note - Remote directory listings are gathered via SFTP when
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

        :raises: :py:class:`pssh.exceptions.SCPError` on errors copying file.
        :raises: :py:class:`IOError` on local file IO errors.
        :raises: :py:class:`OSError` on local OS errors like permission denied.
        """
        if recurse:
            sftp = self._make_sftp() if sftp is None else sftp
            return self._scp_recv_recursive(remote_file, local_file, sftp, encoding=encoding)
        elif local_file.endswith('/'):
            remote_filename = remote_file.rsplit('/')[-1]
            local_file += remote_filename
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
            while total < fileinfo.st_size:
                size, data = file_chan.read(size=fileinfo.st_size - total)
                if size == LIBSSH2_ERROR_EAGAIN:
                    self.poll()
                    continue
                total += size
                local_fh.write(data)
        finally:
            local_fh.close()
            file_chan.close()

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
        if recurse:
            destination = self._remote_paths_split(remote_file)
            if destination is not None:
                sftp = self._make_sftp() if sftp is None else sftp
                try:
                    self._eagain(sftp.stat, destination)
                except (SFTPHandleError, SFTPProtocolError):
                    self.mkdir(sftp, destination)
        elif remote_file.endswith('/'):
            local_filename = local_file.rsplit('/')[-1]
            remote_file += local_filename
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
                    self.eagain_write(chan.write, data)
        except Exception as ex:
            msg = "Error writing to remote file %s on host %s - %s"
            logger.error(msg, remote_file, self.host, ex)
            raise SCPError(msg, remote_file, self.host, ex)
        finally:
            chan.close()

    def _sftp_openfh(self, open_func, remote_file, *args):
        try:
            fh = self._eagain(open_func, remote_file, *args)
        except Exception as ex:
            raise SFTPError(ex)
        return fh

    def _sftp_get(self, remote_fh, local_file):
        with open(local_file, 'wb') as local_fh:
            for size, data in remote_fh:
                if size == LIBSSH2_ERROR_EAGAIN:
                    self.poll()
                    continue
                local_fh.write(data)

    def sftp_get(self, sftp, remote_file, local_file):
        with self._sftp_openfh(
                sftp.open, remote_file,
                LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as remote_fh:
            try:
                self._sftp_get(remote_fh, local_file)
            except SFTPProtocolError as ex:
                msg = "Error reading from remote file %s - %s"
                logger.error(msg, remote_file, ex)
                raise SFTPIOError(msg, remote_file, ex)

    def get_exit_status(self, channel):
        """Get exit status code for channel or ``None`` if not ready.

        :param channel: The channel to get status from.
        :type channel: :py:mod:`ssh2.channel.Channel`
        :rtype: int or ``None``
        """
        if not channel.eof():
            return
        return channel.get_exit_status()

    def finished(self, channel):
        """Checks if remote command has finished - has server sent client
        EOF.

        :rtype: bool
        """
        if channel is None:
            return
        return channel.eof()

    def poll(self, timeout=None):
        """Perform co-operative gevent poll on ssh2 session socket.

        Blocks current greenlet only if socket has pending read or write operations
        in the appropriate direction.
        """
        self._poll_errcodes(
            self.session.block_directions,
            LIBSSH2_SESSION_BLOCK_INBOUND,
            LIBSSH2_SESSION_BLOCK_OUTBOUND,
            timeout=timeout,
        )

    def _eagain_write(self, write_func, data, timeout=None):
        """Write data with given write_func for an ssh2-python session while
        handling EAGAIN and resuming writes from last written byte on each call to
        write_func.
        """
        return self._eagain_write_errcode(write_func, data, LIBSSH2_ERROR_EAGAIN, timeout=timeout)

    def eagain_write(self, write_func, data, timeout=None):
        return self._eagain_write(write_func, data, timeout=timeout)
