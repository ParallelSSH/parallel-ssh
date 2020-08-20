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
from collections import deque
from gevent import sleep, joinall
from gevent.lock import RLock

from ..base_pssh import BaseParallelSSHClient
from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from .single import SSHClient
from ...exceptions import ProxyError, Timeout, HostArgumentException
from .tunnel import Tunnel
from .common import _validate_pkey_path


logger = logging.getLogger(__name__)


class ParallelSSHClient(BaseParallelSSHClient):
    """ssh2-python based parallel client."""

    def __init__(self, hosts, user=None, password=None, port=22, pkey=None,
                 num_retries=DEFAULT_RETRIES, timeout=None, pool_size=10,
                 allow_agent=True, host_config=None, retry_delay=RETRY_DELAY,
                 proxy_host=None, proxy_port=22,
                 proxy_user=None, proxy_password=None, proxy_pkey=None,
                 forward_ssh_agent=False, tunnel_timeout=None,
                 keepalive_seconds=60):
        """
        :param hosts: Hosts to connect to
        :type hosts: list(str)
        :param user: (Optional) User to login as. Defaults to logged in user
        :type user: str
        :param password: (Optional) Password to use for login. Defaults to
          no password
        :type password: str
        :param port: (Optional) Port number to use for SSH connection. Defaults
          to 22.
        :type port: int
        :param pkey: Private key file path to use. Path must be either absolute
          path or relative to user home directory like ``~/<path>``.
        :type pkey: str
        :param num_retries: (Optional) Number of connection and authentication
          attempts before the client gives up. Defaults to 3.
        :type num_retries: int
        :param retry_delay: Number of seconds to wait between retries. Defaults
          to :py:class:`pssh.constants.RETRY_DELAY`
        :type retry_delay: int
        :param timeout: (Optional) SSH session timeout setting in seconds.
          This controls timeout setting of socket operations used for SSH
          sessions. Defaults to OS default - usually 60 seconds.
        :type timeout: float
        :param pool_size: (Optional) Greenlet pool size. Controls
          concurrency, on how many hosts to execute tasks in parallel.
          Defaults to 10. Overhead in event
          loop will determine how high this can be set to, see scaling guide
          lines in project's readme.
        :type pool_size: int
        :param host_config: (Optional) Per-host configuration for cases where
          not all hosts use the same configuration.
        :type host_config: dict
        :param allow_agent: (Optional) set to False to disable connecting to
          the system's SSH agent.
        :type allow_agent: bool
        :param proxy_host: (Optional) SSH host to tunnel connection through
          so that SSH clients connect to host via client -> proxy_host -> host
        :type proxy_host: str
        :param proxy_port: (Optional) SSH port to use to login to proxy host if
          set. Defaults to 22.
        :type proxy_port: int
        :param proxy_user: (Optional) User to login to ``proxy_host`` as.
          Defaults to logged in user.
        :type proxy_user: str
        :param proxy_password: (Optional) Password to login to ``proxy_host``
          with. Defaults to no password.
        :type proxy_password: str
        :param proxy_pkey: (Optional) Private key file to be used for
          authentication with ``proxy_host``. Defaults to available keys from
          SSHAgent and user's SSH identities.
        :type proxy_pkey: Private key file path to use.
        :param forward_ssh_agent: (Optional) Turn on SSH agent forwarding -
          equivalent to `ssh -A` from the `ssh` command line utility.
          Defaults to False if not set.
          Requires agent forwarding implementation in libssh2 version used.
        :type forward_ssh_agent: bool
        :param tunnel_timeout: (Optional) Timeout setting for proxy tunnel
          connections.
        :type tunnel_timeout: float

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        BaseParallelSSHClient.__init__(
            self, hosts, user=user, password=password, port=port, pkey=pkey,
            allow_agent=allow_agent, num_retries=num_retries,
            timeout=timeout, pool_size=pool_size,
            host_config=host_config, retry_delay=retry_delay)
        self.pkey = _validate_pkey_path(pkey)
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_pkey = _validate_pkey_path(proxy_pkey)
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password
        self.forward_ssh_agent = forward_ssh_agent
        self._tunnel = None
        self._tunnel_in_q = None
        self._tunnel_out_q = None
        self._tunnel_lock = None
        self._tunnel_timeout = tunnel_timeout
        self._clients_lock = RLock()
        self.keepalive_seconds = keepalive_seconds

    def run_command(self, command, sudo=False, user=None, stop_on_errors=True,
                    use_pty=False, host_args=None, shell=None,
                    encoding='utf-8', timeout=None, greenlet_timeout=None,
                    return_list=False):
        """Run command on all hosts in parallel, honoring self.pool_size,
        and return output dictionary.

        This function will block until all commands have been received
        by remote servers and then return immediately.

        More explicitly, function will return after connection and
        authentication establishment and after commands have been accepted by
        successfully established SSH channels.

        Any connection and/or authentication exceptions will be raised here
        and need catching *unless* ``run_command`` is called with
        ``stop_on_errors=False`` in which case exceptions are added to
        individual host output instead.

        :param command: Command to run
        :type command: str
        :param sudo: (Optional) Run with sudo. Defaults to False
        :type sudo: bool
        :param user: (Optional) User to run command as. Requires sudo access
          for that user from the logged in user account.
        :type user: str
        :param stop_on_errors: (Optional) Raise exception on errors running
          command. Defaults to True. With stop_on_errors set to False,
          exceptions are instead added to output of `run_command`. See example
          usage below.
        :type stop_on_errors: bool
        :param shell: (Optional) Override shell to use to run command with.
          Defaults to login user's defined shell. Use the shell's command
          syntax, eg `shell='bash -c'` or `shell='zsh -c'`.
        :type shell: str
        :param use_pty: (Optional) Enable/Disable use of pseudo terminal
          emulation. Disabling it will prohibit capturing standard input/output.
          This is required in majority of cases, exceptions being where a shell
          is not used and/or input/output is not required. In particular
          when running a command which deliberately closes input/output pipes,
          such as a daemon process, you may want to disable ``use_pty``.
          Defaults to ``True``
        :type use_pty: bool
        :param host_args: (Optional) Format command string with per-host
          arguments in ``host_args``. ``host_args`` length must equal length of
          host list - :py:class:`pssh.exceptions.HostArgumentException` is
          raised otherwise
        :type host_args: tuple or list
        :param encoding: Encoding to use for output. Must be valid
          `Python codec <https://docs.python.org/library/codecs.html>`_
        :type encoding: str
        :param timeout: (Optional) Timeout in seconds for reading from stdout
          or stderr. Defaults to no timeout. Reading from stdout/stderr will
          raise :py:class:`pssh.exceptions.Timeout`
          after ``timeout`` number seconds if remote output is not ready.
        :type timeout: int
        :param greenlet_timeout: (Optional) Greenlet timeout setting.
          Defaults to no timeout. If set, this function will raise
          :py:class:`gevent.Timeout` after ``greenlet_timeout`` seconds
          if no result is available from greenlets.
          In some cases, such as when using proxy hosts, connection timeout
          is controlled by proxy server and getting result from greenlets may
          hang indefinitely if remote server is unavailable. Use this setting
          to avoid blocking in such circumstances.
          Note that ``gevent.Timeout`` is a special class that inherits from
          ``BaseException`` and thus **can not be caught** by
          ``stop_on_errors=False``.
        :type greenlet_timeout: float
        :param return_list: (Optional) Return a list of ``HostOutput`` objects
          instead of dictionary. ``run_command`` will return a list starting
          from 2.0.0 - enable this flag to avoid client code breaking on
          upgrading to 2.0.0.
        :type return_list: bool
        :rtype: Dictionary with host as key and
          :py:class:`pssh.output.HostOutput` as value
          *or* list(:py:class:`pssh.output.HostOutput`) when
          ``return_list=True``
        :raises: :py:class:`pssh.exceptions.AuthenticationException` on
          authentication error
        :raises: :py:class:`pssh.exceptions.UnknownHostException` on DNS
          resolution error
        :raises: :py:class:`pssh.exceptions.ConnectionErrorException` on error
          connecting
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
          host arguments not equal to number of hosts
        :raises: :py:class:`TypeError` on not enough host arguments for cmd
          string format
        :raises: :py:class:`KeyError` on no host argument key in arguments
          dict for cmd string format
        :raises: :py:class:`pssh.exceptions.ProxyError` on errors connecting
          to proxy if a proxy host has been set.
        :raises: :py:class:`gevent.Timeout` on greenlet timeout. Gevent timeout
          can not be caught by ``stop_on_errors=False``.
        :raises: Exceptions from :py:mod:`ssh2.exceptions` for all other
          specific errors such as
          :py:class:`ssh2.exceptions.SocketDisconnectError` et al.
        """
        return BaseParallelSSHClient.run_command(
            self, command, stop_on_errors=stop_on_errors, host_args=host_args,
            user=user, shell=shell, sudo=sudo,
            encoding=encoding, use_pty=use_pty, timeout=timeout,
            greenlet_timeout=greenlet_timeout, return_list=return_list)

    def __del__(self):
        if not hasattr(self, '_host_clients'):
            return
        logger.debug("Disconnecting clients")
        for s_client in self._host_clients.values():
            try:
                s_client.disconnect()
            except Exception as ex:
                logger.debug("Client disconnect failed with %s", ex)
                pass
            del s_client

    def join(self, output, consume_output=False, timeout=None,
             encoding='utf-8'):
        """Wait until all remote commands in output have finished
        and retrieve exit codes. Does *not* block other commands from
        running in parallel.

        :param output: Output of commands to join on
        :type output: `HostOutput` objects
        :param consume_output: Whether or not join should consume output
          buffers. Output buffers will be empty after ``join`` if set
          to ``True``. Must be set to ``True`` to allow host logger to log
          output on call to ``join`` when host logger has been enabled.
        :type consume_output: bool
        :param timeout: Timeout in seconds if remote command is not yet
          finished. Note that use of timeout forces ``consume_output=True``
          otherwise the channel output pending to be consumed always results
          in the channel not being finished.
        :type timeout: int
        :param encoding: Encoding to use for output. Must be valid
          `Python codec <https://docs.python.org/library/codecs.html>`_
        :type encoding: str

        :raises: :py:class:`pssh.exceptions.Timeout` on timeout requested and
          reached with commands still running.

        :rtype: ``None``"""
        cmds = []
        if isinstance(output, list):
            for host_i, host_out in enumerate(output):
                host = self.hosts[host_i]
                cmds.append(self.pool.spawn(
                    self._join, host_out,
                    consume_output=consume_output, timeout=timeout))
        elif isinstance(output, dict):
            for host_i, (host, host_out) in enumerate(output.items()):
                cmds.append(self.pool.spawn(
                    self._join, host_out,
                    consume_output=consume_output, timeout=timeout))
        else:
            raise ValueError("Unexpected output object type")
        # Errors raised by self._join should be propagated.
        # Timeouts are handled by self._join itself.
        joinall(cmds, raise_error=True)

    def _join(self, host_out, consume_output=False, timeout=None,
              encoding="utf-8"):
        if host_out is None:
            return
        channel = host_out.channel
        client = host_out.client
        host = host_out.host
        if client is None:
            return
        stdout, stderr = self.reset_output_generators(
            host_out, channel=channel, timeout=timeout,
            encoding=encoding)
        try:
            client.wait_finished(channel, timeout=timeout)
        except Timeout:
            raise Timeout(
                "Timeout of %s sec(s) reached on host %s with command "
                "still running", timeout, host)
        if timeout:
            # Must consume buffers prior to EOF check
            self._consume_output(stdout, stderr)
            if not channel.eof():
                raise Timeout(
                    "Timeout of %s sec(s) reached on host %s with command "
                    "still running", timeout, host)
        elif consume_output:
            self._consume_output(stdout, stderr)

    def reset_output_generators(self, host_out, timeout=None,
                                client=None, channel=None,
                                encoding='utf-8'):
        """Reset output generators for host output. This creates new
        generators for stdout and stderr for the provided host output, useful
        in cases where the previous generators have raised a Timeout but the
        remote command is still running.

        :param host_out: Host output
        :type host_out: :py:class:`pssh.output.HostOutput`
        :param client: (Optional) SSH client
        :type client: :py:class:`pssh.ssh2_client.SSHClient`
        :param channel: (Optional) SSH channel
        :type channel: :py:class:`ssh2.channel.Channel`
        :param timeout: (Optional) Timeout setting
        :type timeout: int
        :param encoding: (Optional) Encoding to use for output. Must be valid
          `Python codec <https://docs.python.org/library/codecs.html>`_
        :type encoding: str

        :rtype: tuple(stdout, stderr)
        """
        channel = host_out.channel if channel is None else channel
        client = host_out.client if client is None else client
        stdout = client.read_output_buffer(
            client.read_output(channel, timeout=timeout), encoding=encoding)
        stderr = client.read_output_buffer(
            client.read_stderr(channel, timeout=timeout),
            prefix='\t[err]', encoding=encoding)
        host_out.stdout = stdout
        host_out.stderr = stderr
        return stdout, stderr

    def _consume_output(self, stdout, stderr):
        for line in stdout:
            pass
        for line in stderr:
            pass

    def _start_tunnel_thread(self):
        self._tunnel_lock = RLock()
        self._tunnel_in_q = deque()
        self._tunnel_out_q = deque()
        self._tunnel = Tunnel(
            self.proxy_host, self._tunnel_in_q, self._tunnel_out_q,
            user=self.proxy_user,
            password=self.proxy_password, port=self.proxy_port,
            pkey=self.proxy_pkey, num_retries=self.num_retries,
            timeout=self._tunnel_timeout, retry_delay=self.retry_delay,
            allow_agent=self.allow_agent)
        self._tunnel.daemon = True
        self._tunnel.start()
        while not self._tunnel.tunnel_open.is_set():
            logger.debug("Waiting for tunnel to become active")
            sleep(.1)
            if not self._tunnel.is_alive():
                msg = "Proxy authentication failed. " \
                      "Exception from tunnel client: %s"
                logger.error(msg, self._tunnel.exception)
                raise ProxyError(msg, self._tunnel.exception)

    def _make_ssh_client(self, host_i, host):
        auth_thread_pool = True
        if self.proxy_host is not None and self._tunnel is None:
            self._start_tunnel_thread()
        logger.debug("Make client request for host %s, host in clients: %s",
                     host, host in self.host_clients)
        with self._clients_lock:
            if (host_i, host) not in self._host_clients \
               or self._host_clients[(host_i, host)] is None:
                _user, _port, _password, _pkey = self._get_host_config_values(
                    host)
                proxy_host = None if self.proxy_host is None else '127.0.0.1'
                if proxy_host is not None:
                    auth_thread_pool = False
                    _wait = 0.0
                    max_wait = self.timeout if self.timeout is not None else 60
                    with self._tunnel_lock:
                        self._tunnel_in_q.append((host, _port))
                    while True:
                        if _wait >= max_wait:
                            raise Timeout("Timed out waiting on tunnel to "
                                          "open listening port")
                        try:
                            _port = self._tunnel_out_q.pop()
                        except IndexError:
                            logger.debug(
                                "Waiting on tunnel to open listening port")
                            sleep(.5)
                            _wait += .5
                        else:
                            break
                _client = SSHClient(
                    host, user=_user, password=_password, port=_port,
                    pkey=_pkey, num_retries=self.num_retries,
                    timeout=self.timeout,
                    allow_agent=self.allow_agent, retry_delay=self.retry_delay,
                    proxy_host=proxy_host, _auth_thread_pool=auth_thread_pool,
                    forward_ssh_agent=self.forward_ssh_agent,
                    keepalive_seconds=self.keepalive_seconds)
                self.host_clients[host] = _client
                self._host_clients[(host_i, host)] = _client
                return _client
        return self._host_clients[(host_i, host)]

    def copy_file(self, local_file, remote_file, recurse=False, copy_args=None):
        """Copy local file to remote file in parallel via SFTP.

        This function returns a list of greenlets which can be
        `join`-ed on to wait for completion.

        :py:func:`gevent.joinall` function may be used to join on all greenlets
        and will also raise exceptions from them if called with
        ``raise_error=True`` - default is `False`.

        Alternatively call `.get()` on each greenlet to raise any exceptions
        from it.

        Exceptions listed here are raised when
        either ``gevent.joinall(<greenlets>, raise_error=True)``
        or ``.get()`` on each greenlet are called, not this function itself.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool
        :param copy_args: (Optional) format local_file and remote_file strings
          with per-host arguments in ``copy_args``. ``copy_args`` length must
          equal length of host list -
          :py:class:`pssh.exceptions.HostArgumentException` is raised otherwise
        :type copy_args: tuple or list

        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
          per-host copy arguments not equal to number of hosts
        :raises: :py:class:`pss.exceptions.SFTPError` on SFTP initialisation
          errors
        :raises: :py:class:`pssh.exceptions.SFTPIOError` on I/O errors writing
          via SFTP
        :raises: :py:class:`OSError` on local OS errors like permission denied

        .. note ::

          Remote directories in ``remote_file`` that do not exist will be
          created as long as permissions allow.

        """
        return BaseParallelSSHClient.copy_file(
            self, local_file, remote_file, recurse=recurse, copy_args=copy_args)

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         suffix_separator='_', copy_args=None,
                         encoding='utf-8'):
        """Copy remote file(s) in parallel via SFTP as
        <local_file><suffix_separator><host>

        With a ``local_file`` value of ``myfile`` and default separator ``_``
        the resulting filename will be ``myfile_myhost`` for the file from host
        ``myhost``.

        This function, like :py:func:`ParallelSSHClient.copy_file`, returns a
        list of greenlets which can be `join`-ed on to wait for completion.

        :py:func:`gevent.joinall` function may be used to join on all greenlets
        and will also raise exceptions if called with ``raise_error=True`` -
        default is `False`.

        Alternatively call `.get` on each greenlet to raise any exceptions from
        it.

        Exceptions listed here are raised when
        either ``gevent.joinall(<greenlets>, raise_error=True)`` is called
        or ``.get`` is called on each greenlet, not this function itself.

        :param remote_file: remote filepath to copy to local host
        :type remote_file: str
        :param local_file: local filepath on local host to copy file to
        :type local_file: str
        :param recurse: whether or not to recurse
        :type recurse: bool
        :param suffix_separator: (Optional) Separator string between
          filename and host, defaults to ``_``. For example, for a
          ``local_file`` value of ``myfile`` and default separator the
          resulting filename will be ``myfile_myhost`` for the file from
          host ``myhost``. ``suffix_separator`` has no meaning if
          ``copy_args`` is provided
        :type suffix_separator: str
        :param copy_args: (Optional) format remote_file and local_file strings
          with per-host arguments in ``copy_args``.   ``copy_args`` length must
          equal length of host list -
          :py:class:`pssh.exceptions.HostArgumentException` is raised otherwise
        :type copy_args: tuple or list
        :param encoding: Encoding to use for file paths.
        :type encoding: str

        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
          per-host copy arguments not equal to number of hosts
        :raises: :py:class:`pss.exceptions.SFTPError` on SFTP initialisation
          errors
        :raises: :py:class:`pssh.exceptions.SFTPIOError` on I/O errors reading
          from SFTP
        :raises: :py:class:`OSError` on local OS errors like permission denied

        .. note ::
          Local directories in `local_file` that do not exist will be
          created as long as permissions allow.

        .. note ::
          File names will be de-duplicated by appending the hostname to the
          filepath separated by ``suffix_separator``.

        """
        return BaseParallelSSHClient.copy_remote_file(
            self, remote_file, local_file, recurse=recurse,
            suffix_separator=suffix_separator, copy_args=copy_args,
            encoding=encoding)

    def _scp_send(self, host_i, host, local_file, remote_file, recurse=False):
        self._make_ssh_client(host_i, host)
        return self._handle_greenlet_exc(
            self._host_clients[(host_i, host)].scp_send, host,
            local_file, remote_file, recurse=recurse)

    def _scp_recv(self, host_i, host, remote_file, local_file, recurse=False):
        self._make_ssh_client(host_i, host)
        return self._handle_greenlet_exc(
            self._host_clients[(host_i, host)].scp_recv, host,
            remote_file, local_file, recurse=recurse)

    def scp_send(self, local_file, remote_file, recurse=False):
        """Copy local file to remote file in parallel via SCP.

        This function returns a list of greenlets which can be
        `join`-ed on to wait for completion.

        :py:func:`gevent.joinall` function may be used to join on all greenlets
        and will also raise exceptions from them if called with
        ``raise_error=True`` - default is `False`.

        Alternatively call `.get()` on each greenlet to raise any exceptions
        from it.

        .. note::
          Creating remote directories when either ``remote_file`` contains
          directory paths or ``recurse`` is enabled requires SFTP support on
          the server as libssh2 SCP implementation lacks directory creation
          support.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool

        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands.

        :raises: :py:class:`pss.exceptions.SCPError` on errors copying file.
        :raises: :py:class:`OSError` on local OS errors like permission denied.
        """
        return [self.pool.spawn(self._scp_send, host_i, host, local_file,
                                remote_file, recurse=recurse)
                for host_i, host in enumerate(self.hosts)]

    def scp_recv(self, remote_file, local_file, recurse=False, copy_args=None,
                 suffix_separator='_'):
        """Copy remote file(s) in parallel via SCP as
        <local_file><suffix_separator><host> or as per ``copy_args`` argument.

        With a ``local_file`` value of ``myfile`` and default separator ``_``
        the resulting filename will be ``myfile_myhost`` for the file from host
        ``myhost``.

        De-duplication behaviour is configurable by providing ``copy_args``
        argument, see below.

        This function, like :py:func:`ParallelSSHClient.scp_send`, returns a
        list of greenlets which can be `join`-ed on to wait for completion.

        :py:func:`gevent.joinall` function may be used to join on all greenlets
        and will also raise exceptions if called with ``raise_error=True`` -
        default is `False`.

        Alternatively call `.get` on each greenlet to raise any exceptions from
        it.

        Exceptions listed here are raised when
        either ``gevent.joinall(<greenlets>, raise_error=True)`` is called
        or ``.get`` is called on each greenlet, not this function itself.

        :param remote_file: remote filepath to copy to local host
        :type remote_file: str
        :param local_file: local filepath on local host to copy file to
        :type local_file: str
        :param recurse: whether or not to recurse
        :type recurse: bool
        :param suffix_separator: (Optional) Separator string between
          filename and host, defaults to ``_``. For example, for a
          ``local_file`` value of ``myfile`` and default separator the
          resulting filename will be ``myfile_myhost`` for the file from
          host ``myhost``. ``suffix_separator`` has no meaning if
          ``copy_args`` is provided
        :type suffix_separator: str
        :param copy_args: (Optional) format remote_file and local_file strings
          with per-host arguments in ``copy_args``. ``copy_args`` length *must*
          equal length of host list -
          :py:class:`pssh.exceptions.HostArgumentException` is raised otherwise
        :type copy_args: tuple or list

        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands.

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set.
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
          per-host copy arguments not equal to number of hosts.
        :raises: :py:class:`pss.exceptions.SCPError` on errors copying file.
        :raises: :py:class:`OSError` on local OS errors like permission denied.

        .. note ::
          Local directories in ``local_file`` that do not exist will be
          created as long as permissions allow.

        .. note ::
          File names will be de-duplicated by appending the hostname to the
          filepath separated by ``suffix_separator`` or as per ``copy_args``
          argument if provided.
        """
        copy_args = [{'local_file': suffix_separator.join([local_file, host]),
                      'remote_file': remote_file}
                     for i, host in enumerate(self.hosts)] \
            if copy_args is None else copy_args
        local_file = "%(local_file)s"
        remote_file = "%(remote_file)s"
        try:
            return [self.pool.spawn(
                self._scp_recv, host_i, host,
                remote_file % copy_args[host_i],
                local_file % copy_args[host_i], recurse=recurse)
                    for host_i, host in enumerate(self.hosts)]
        except IndexError:
            raise HostArgumentException(
                "Number of per-host copy arguments provided does not match "
                "number of hosts")

    def _handle_greenlet_exc(self, func, host, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            ex.host = host
            raise ex
