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

from gevent import sleep, spawn, get_hub, Timeout as GTimeout
from gevent.select import POLLIN, POLLOUT
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh2.exceptions import SFTPHandleError, SFTPProtocolError, \
    Timeout as SSH2Timeout, AgentConnectionError, AgentListIdentitiesError, \
    AgentAuthenticationError, AgentGetIdentityError
from ssh2.session import Session, LIBSSH2_SESSION_BLOCK_INBOUND, LIBSSH2_SESSION_BLOCK_OUTBOUND
from ssh2.sftp import LIBSSH2_FXF_READ, LIBSSH2_FXF_CREAT, LIBSSH2_FXF_WRITE, \
    LIBSSH2_FXF_TRUNC, LIBSSH2_SFTP_S_IRUSR, LIBSSH2_SFTP_S_IRGRP, \
    LIBSSH2_SFTP_S_IWUSR, LIBSSH2_SFTP_S_IXUSR, LIBSSH2_SFTP_S_IROTH, \
    LIBSSH2_SFTP_S_IXGRP, LIBSSH2_SFTP_S_IXOTH
from ssh2.utils import find_eol

from ..base.single import BaseSSHClient
from ...exceptions import AuthenticationException, SessionError, SFTPError, \
    SFTPIOError, Timeout, SCPError
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)
THREAD_POOL = get_hub().threadpool


class SSHClient(BaseSSHClient):
    """ssh2-python (libssh2) based non-blocking SSH client."""

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 forward_ssh_agent=False,
                 proxy_host=None,
                 _auth_thread_pool=True, keepalive_seconds=60,
                 identity_auth=True,):
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
        :param identity_auth: (Optional) set to False to disable attempting to
          authenticate with default identity files from
          `pssh.clients.base_ssh_client.BaseSSHClient.IDENTITIES`
        :type identity_auth: bool
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
        self.forward_ssh_agent = forward_ssh_agent
        self._forward_requested = False
        self.keepalive_seconds = keepalive_seconds
        self._keepalive_greenlet = None
        super(SSHClient, self).__init__(
            host, user=user, password=password, port=port, pkey=pkey,
            num_retries=num_retries, retry_delay=retry_delay,
            allow_agent=allow_agent, _auth_thread_pool=_auth_thread_pool,
            timeout=timeout,
            proxy_host=proxy_host, identity_auth=identity_auth)

    def disconnect(self):
        """Disconnect session, close socket if needed."""
        self._keepalive_greenlet = None
        if self.session is not None:
            try:
                self._eagain(self.session.disconnect)
            except Exception:
                pass
            self.session = None
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
            ex.host = self.host
            ex.port = self.port
            raise

    def _keepalive(self):
        if self.keepalive_seconds:
            self.configure_keepalive()
            self._keepalive_greenlet = self.spawn_send_keepalive()

    def auth(self):
        if self.pkey is not None:
            logger.debug(
                "Proceeding with private key file authentication")
            return self._pkey_auth(password=self.password)
        if self.allow_agent:
            try:
                self.session.agent_auth(self.user)
            except (AgentAuthenticationError, AgentConnectionError, AgentGetIdentityError,
                    AgentListIdentitiesError) as ex:
                logger.debug("Agent auth failed with %s"
                             "continuing with other authentication methods", ex)
            except Exception as ex:
                logger.error("Unknown error during agent authentication - %s", ex)
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

    def _pkey_auth(self, password=None):
        self.session.userauth_publickey_fromfile(
            self.user,
            self.pkey,
            passphrase=password if password is not None else '')

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
            self.poll()
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
        logger.debug("Executing command '%s'", cmd)
        self._eagain(channel.execute, cmd)
        return channel

    def _read_output(self, read_func, timeout=None):
        remainder = b""
        remainder_len = 0
        size, data = read_func()
        t = GTimeout(seconds=timeout, exception=Timeout)
        t.start()
        try:
            while size == LIBSSH2_ERROR_EAGAIN or size > 0:
                while size == LIBSSH2_ERROR_EAGAIN:
                    self.poll(timeout=timeout)
                    size, data = read_func()
                while size > 0:
                    pos = 0
                    while pos < size:
                        linesep, new_line_pos = find_eol(data, pos)
                        if linesep == -1:
                            remainder += data[pos:]
                            remainder_len = len(remainder)
                            break
                        end_of_line = pos+linesep
                        if remainder_len > 0:
                            line = remainder + data[pos:end_of_line]
                            remainder = b""
                            remainder_len = 0
                        else:
                            line = data[pos:end_of_line]
                        yield line
                        pos += linesep + new_line_pos
                    size, data = read_func()
            if remainder_len > 0:
                # Finished reading without finding ending linesep
                yield remainder
        finally:
            t.close()

    def read_stderr(self, channel, timeout=None):
        """Read standard error buffer from channel.
        Returns a generator of line by line output.

        :param channel: Channel to read output from.
        :type channel: :py:class:`ssh2.channel.Channel`
        :rtype: generator
        """
        return self._read_output(channel.read_stderr, timeout=timeout)

    def read_output(self, channel, timeout=None):
        """Read standard output buffer from channel.
        Returns a generator of line by line output.

        :param channel: Channel to read output from.
        :type channel: :py:class:`ssh2.channel.Channel`
        :rtype: generator
        """
        return self._read_output(channel.read, timeout=timeout)

    def wait_finished(self, channel, timeout=None):
        """Wait for EOF from channel and close channel.

        Used to wait for remote command completion and be able to gather
        exit code.

        :param channel: The channel to use.
        :type channel: :py:class:`ssh2.channel.Channel`
        :param timeout: Timeout value in seconds - defaults to no timeout.
        :type timeout: float

        :raises: :py:class:`pssh.exceptions.Timeout` after <timeout> seconds if
          timeout given.
        """
        if channel is None:
            return
        self._eagain(channel.wait_eof, timeout=timeout)
        # Close channel to indicate no more commands will be sent over it
        self.close_channel(channel)

    def close_channel(self, channel):
        logger.debug("Closing channel")
        self._eagain(channel.close)

    def _eagain(self, func, *args, **kwargs):
        timeout = kwargs.pop('timeout', self.timeout)
        with GTimeout(seconds=timeout, exception=Timeout):
            ret = func(*args, **kwargs)
            while ret == LIBSSH2_ERROR_EAGAIN:
                self.poll()
                ret = func(*args, **kwargs)
            return ret

    def _make_sftp(self):
        """Make SFTP client from open transport"""
        try:
            sftp = self.session.sftp_init()
        except Exception as ex:
            raise SFTPError(ex)
        while sftp == LIBSSH2_ERROR_EAGAIN:
            self.poll()
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

    def copy_file(self, local_file, remote_file, recurse=False, sftp=None):
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
                self.eagain_write(remote_fh.write, data)

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

        :raises: :py:class:`pssh.exceptions.SCPError` when a directory is
          supplied to ``local_file`` and ``recurse`` is not set.
        :raises: :py:class:`pssh.exceptions.SCPError` on errors copying file.
        :raises: :py:class:`IOError` on local file IO errors.
        :raises: :py:class:`OSError` on local OS errors like permission denied.
        """
        if recurse:
            sftp = self._make_sftp() if sftp is None else sftp
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
                try:
                    os.makedirs(local_file)
                except OSError:
                    pass
                file_list = self._sftp_readdir(dir_h)
                return self._scp_recv_dir(file_list, remote_file,
                                          local_file, sftp,
                                          encoding=encoding)
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
            if total != fileinfo.st_size:
                msg = "Error copying data from remote file %s on host %s. " \
                      "Copied %s out of %s total bytes"
                raise SCPError(msg, remote_file, self.host, total,
                               fileinfo.st_size)
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
            fh = open_func(remote_file, *args)
        except Exception as ex:
            raise SFTPError(ex)
        while fh == LIBSSH2_ERROR_EAGAIN:
            self.poll(timeout=0.1)
            try:
                fh = open_func(remote_file, *args)
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
                # Running SFTP in a thread requires a new session
                # as session handles or any handles created by a session
                # cannot be used simultaneously in multiple threads.
                # THREAD_POOL.apply(
                #     sftp_get, args=(self.session, remote_fh, local_file))
            except SFTPProtocolError as ex:
                msg = "Error reading from remote file %s - %s"
                logger.error(msg, remote_file, ex)
                raise SFTPIOError(msg, remote_file, ex)

    def get_exit_status(self, channel):
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
        directions = self.session.block_directions()
        if directions == 0:
            return
        events = 0
        if directions & LIBSSH2_SESSION_BLOCK_INBOUND:
            events = POLLIN
        if directions & LIBSSH2_SESSION_BLOCK_OUTBOUND:
            events |= POLLOUT
        self._poll_socket(events, timeout=timeout)

    def eagain_write(self, write_func, data, timeout=None):
        """Write data with given write_func for an ssh2-python session while
        handling EAGAIN and resuming writes from last written byte on each call to
        write_func.
        """
        data_len = len(data)
        total_written = 0
        while total_written < data_len:
            rc, bytes_written = write_func(data[total_written:])
            total_written += bytes_written
            if rc == LIBSSH2_ERROR_EAGAIN:
                self.poll(timeout=timeout)
