# This file is part of parallel-ssh.

# Copyright (C) 2014-2018 Panos Kittenis

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

import logging
from gevent import sleep

from .base_pssh import BaseParallelSSHClient
from .constants import DEFAULT_RETRIES, RETRY_DELAY
from .ssh2_client import SSHClient
from .exceptions import ProxyError, Timeout
from .tunnel import Tunnel


logger = logging.getLogger(__name__)


class ParallelSSHClient(BaseParallelSSHClient):
    """ssh2-python based parallel client."""

    def __init__(self, hosts, user=None, password=None, port=None, pkey=None,
                 num_retries=DEFAULT_RETRIES, timeout=None, pool_size=10,
                 allow_agent=True, host_config=None, retry_delay=RETRY_DELAY,
                 proxy_host=None, proxy_port=22,
                 proxy_user=None, proxy_password=None, proxy_pkey=None):
        """
        :param hosts: Hosts to connect to
        :type hosts: list(str)
        :param user: (Optional) User to login as. Defaults to logged in user
        :type user: str
        :param password: (Optional) Password to use for login. Defaults to
          no password
        :type password: str
        :param port: (Optional) Port number to use for SSH connection. Defaults
          to ``None`` which uses SSH default (22)
        :type port: int
        :param pkey: Private key file path to use. Note that the public key file
          pair *must* also exist in the same location with name ``<pkey>.pub``
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
        :type proxy_pkey: Private key file path to use. Note that the public
          key file pair *must* also exist in the same location with name
          ``<pkey>.pub``.
        """
        BaseParallelSSHClient.__init__(
            self, hosts, user=user, password=password, port=port, pkey=pkey,
            allow_agent=allow_agent, num_retries=num_retries,
            timeout=timeout, pool_size=pool_size,
            host_config=host_config, retry_delay=retry_delay)
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_pkey = proxy_pkey
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password
        self._tunnels = {}

    def run_command(self, command, sudo=False, user=None, stop_on_errors=True,
                    use_pty=False, host_args=None, shell=None,
                    encoding='utf-8', timeout=None):
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
          `Python codec <https://docs.python.org/2.7/library/codecs.html>`_
        :type encoding: str
        :param timeout: (Optional) Timeout in seconds for reading from stdout
          or stderr. Defaults to no timeout. Reading from stdout/stderr will
          timeout after this many seconds if remote output is not ready.
        :type timeout: int

        :rtype: Dictionary with host as key and
          :py:class:`pssh.output.HostOutput` as value as per
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`

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
        """
        return BaseParallelSSHClient.run_command(
            self, command, stop_on_errors=stop_on_errors, host_args=host_args,
            user=user, shell=shell, sudo=sudo,
            encoding=encoding, use_pty=use_pty, timeout=timeout)

    def _run_command(self, host, command, sudo=False, user=None,
                     shell=None, use_pty=False,
                     encoding='utf-8', timeout=None):
        """Make SSHClient if needed, run command on host"""
        self._make_ssh_client(host)
        return self.host_clients[host].run_command(
            command, sudo=sudo, user=user, shell=shell,
            use_pty=use_pty, encoding=encoding, timeout=timeout)

    def join(self, output, consume_output=False, timeout=None):
        """Wait until all remote commands in output have finished
        and retrieve exit codes. Does *not* block other commands from
        running in parallel.

        :param output: Output of commands to join on
        :type output: dict as returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
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

        :raises: :py:class:`pssh.exceptions.Timeout` on timeout requested and
          reached with commands still running.

        :rtype: ``None``"""
        for host, host_out in output.items():
            if host not in self.host_clients or self.host_clients[host] is None:
                continue
            client = self.host_clients[host]
            channel = host_out.channel
            try:
                client.wait_finished(channel, timeout=timeout)
            except Timeout:
                raise Timeout(
                    "Timeout of %s sec(s) reached on host %s with command "
                    "still running", timeout, host)
            stdout = host_out.stdout
            stderr = host_out.stderr
            if timeout:
                # Must consume buffers prior to EOF check
                self._consume_output(stdout, stderr)
                if not channel.eof():
                    raise Timeout(
                        "Timeout of %s sec(s) reached on host %s with command "
                        "still running", timeout, host)
            elif consume_output:
                self._consume_output(stdout, stderr)
        self.get_exit_codes(output)

    def _consume_output(self, stdout, stderr):
        for line in stdout:
            pass
        for line in stderr:
            pass

    def _get_exit_code(self, channel):
        """Get exit code from channel if ready"""
        if channel is None:
            return
        return channel.get_exit_status()

    def _start_tunnel(self, host):
        if host in self._tunnels:
            return self._tunnels[host]
        tunnel = Tunnel(
            self.proxy_host, host, self.port, user=self.proxy_user,
            password=self.proxy_password, port=self.proxy_port,
            pkey=self.proxy_pkey, num_retries=self.num_retries,
            timeout=self.timeout, retry_delay=self.retry_delay,
            allow_agent=self.allow_agent)
        tunnel.daemon = True
        tunnel.start()
        self._tunnels[host] = tunnel
        while not tunnel.tunnel_open.is_set():
            logger.debug("Waiting for tunnel to become active")
            sleep(.1)
            if not tunnel.is_alive():
                msg = "Proxy authentication failed"
                logger.error(msg)
                raise ProxyError(msg)
        return tunnel

    def _make_ssh_client(self, host):
        if host not in self.host_clients or self.host_clients[host] is None:
            if self.proxy_host is not None:
                tunnel = self._start_tunnel(host)
            _user, _port, _password, _pkey = self._get_host_config_values(host)
            _host = host if self.proxy_host is None else '127.0.0.1'
            _port = _port if self.proxy_host is None else tunnel.listen_port
            self.host_clients[host] = SSHClient(
                _host, user=_user, password=_password, port=_port, pkey=_pkey,
                num_retries=self.num_retries, timeout=self.timeout,
                allow_agent=self.allow_agent, retry_delay=self.retry_delay)

    def copy_file(self, local_file, remote_file, recurse=False):
        """Copy local file to remote file in parallel

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

        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
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
            self, local_file, remote_file, recurse=recurse)

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         suffix_separator='_', encoding='utf-8'):
        """Copy remote file(s) in parallel as
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
          host ``myhost``
        :type suffix_separator: str
        :param encoding: Encoding to use for file paths.
        :type encoding: str

        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
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
            suffix_separator=suffix_separator, encoding=encoding)
