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

import sys
if 'threading' in sys.modules:
    del sys.modules['threading']
from gevent import monkey  # noqa: E402
monkey.patch_all()
import logging  # noqa: E402

import gevent.pool  # noqa: E402
import gevent.hub  # noqa: E402
gevent.hub.Hub.NOT_ERROR = (Exception,)

from .base_pssh import BaseParallelSSHClient  # noqa: E402
from .exceptions import HostArgumentException  # noqa: E402
from .constants import DEFAULT_RETRIES, RETRY_DELAY  # noqa: E402
from .ssh_client import SSHClient  # noqa: E402


logger = logging.getLogger('pssh')


class ParallelSSHClient(BaseParallelSSHClient):
    """Parallel SSH client using paramiko based SSH client"""

    def __init__(self, hosts, user=None, password=None, port=None, pkey=None,
                 forward_ssh_agent=True, num_retries=DEFAULT_RETRIES,
                 timeout=120, pool_size=10, proxy_host=None, proxy_port=22,
                 proxy_user=None, proxy_password=None, proxy_pkey=None,
                 agent=None, allow_agent=True, host_config=None,
                 channel_timeout=None, retry_delay=RETRY_DELAY):
        """
        :param hosts: Hosts to connect to
        :type hosts: list(str)
        :param user: (Optional) User to login as. Defaults to logged in user or
          user from ~/.ssh/config or /etc/ssh/ssh_config if set
        :type user: str
        :param password: (Optional) Password to use for login. Defaults to
          no password
        :type password: str
        :param port: (Optional) Port number to use for SSH connection. Defaults
          to ``None`` which uses SSH default
        :type port: int
        :param pkey: (Optional) Client's private key to be used to connect with
        :type pkey: :py:class:`paramiko.pkey.PKey`
        :param num_retries: (Optional) Number of retries for connection attempts
          before the client gives up. Defaults to 3.
        :type num_retries: int
        :param retry_delay: Number of seconds to wait between retries. Defaults
          to :py:class:`pssh.constants.RETRY_DELAY`
        :type retry_delay: int
        :param timeout: (Optional) Number of seconds to wait before connection
          and authentication attempt times out. Note that total time before
          timeout will be
          ``timeout`` * ``num_retries`` + (5 * (``num_retries``-1)) number of
          seconds, where (5 * (``num_retries``-1)) refers to a five (5) second
          delay between retries.
        :type timeout: int
        :param forward_ssh_agent: (Optional) Turn on/off SSH agent forwarding -
          equivalent to `ssh -A` from the `ssh` command line utility.
          Defaults to ``True`` if not set.
        :type forward_ssh_agent: bool
        :param pool_size: (Optional) Greenlet pool size. Controls on how many
          hosts to execute tasks in parallel. Defaults to 10. Overhead in event
          loop will determine how high this can be set to, see scaling guide
          lines in project's readme.
        :type pool_size: int
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
          with. Defaults to no password
        :type proxy_password: str
        :param proxy_pkey: (Optional) Private key to be used for authentication
          with ``proxy_host``. Defaults to available keys from SSHAgent and
          user's home directory keys
        :type proxy_pkey: :py:class:`paramiko.pkey.PKey`
        :param agent: (Optional) SSH agent object to programmatically supply an
          agent to override system SSH agent with
        :type agent: :py:class:`pssh.agent.SSHAgent`
        :param host_config: (Optional) Per-host configuration for cases where
          not all hosts use the same configuration values.
        :type host_config: dict
        :param channel_timeout: (Optional) Time in seconds before reading from
          an SSH channel times out. For example with channel timeout set to one,
          trying to immediately gather output from a command producing no output
          for more than one second will timeout.
        :type channel_timeout: int
        :param allow_agent: (Optional) set to False to disable connecting to
          the system's SSH agent
        :type allow_agent: bool"""
        BaseParallelSSHClient.__init__(
            self, hosts, user=user, password=password, port=port, pkey=pkey,
            allow_agent=allow_agent, num_retries=num_retries,
            timeout=timeout, pool_size=pool_size,
            host_config=host_config, retry_delay=retry_delay)
        self.forward_ssh_agent = forward_ssh_agent
        self.proxy_host, self.proxy_port, self.proxy_user, \
            self.proxy_password, self.proxy_pkey = proxy_host, proxy_port, \
            proxy_user, proxy_password, proxy_pkey
        self.agent = agent
        self.channel_timeout = channel_timeout

    def run_command(self, command, sudo=False, user=None, stop_on_errors=True,
                    shell=None, use_shell=True, use_pty=True, host_args=None,
                    encoding='utf-8', **paramiko_kwargs):
        """Run command on all hosts in parallel, honoring self.pool_size,
        and return output buffers.

        This function will block until all commands have been received
        by remote servers and then return immediately.

        More explicitly, function will return after connection and
        authentication establishment and after commands have been received by
        successfully established SSH channels.

        Any connection and/or authentication exceptions will be raised here
        and need catching *unless* ``run_command`` is called with
        ``stop_on_errors=False`` in which case exceptions are added to host
        output instead.

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
        :param use_shell: (Optional) Run command with or without shell. Defaults
          to True - use shell defined in user login to run command string
        :type use_shell: bool
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
        :param paramiko_kwargs: (Optional) Extra keyword arguments to be
          passed on to :py:func:`paramiko.client.SSHClient.connect`
        :type paramiko_kwargs: dict

        :rtype: Dictionary with host as key and
          :py:class:`pssh.output.HostOutput` as value as per
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`

        :raises: :py:class:`pssh.exceptions.AuthenticationException` on
          authentication error
        :raises: :py:class:`pssh.exceptions.UnknownHostException` on DNS
          resolution error
        :raises: :py:class:`pssh.exceptions.ConnectionErrorException` on error
          connecting
        :raises: :py:class:`pssh.exceptions.SSHException` on other undefined SSH
          errors
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
          host arguments not equal to number of hosts
        :raises: :py:class:`TypeError` on not enough host arguments for cmd
          string format
        :raises: :py:class:`KeyError` on no host argument key in arguments
          dict for cmd string format"""
        output = {}
        if host_args:
            try:
                cmds = [self.pool.spawn(self._run_command, host,
                                        command % host_args[host_i],
                                        sudo=sudo, user=user, shell=shell,
                                        use_shell=use_shell, use_pty=use_pty,
                                        **paramiko_kwargs)
                        for host_i, host in enumerate(self.hosts)]
            except IndexError:
                raise HostArgumentException(
                    "Number of host arguments provided does not match "
                    "number of hosts ")
        else:
            cmds = [self.pool.spawn(
                self._run_command, host, command,
                sudo=sudo, user=user, shell=shell,
                use_shell=use_shell, use_pty=use_pty,
                **paramiko_kwargs)
                for host in self.hosts]
        for cmd in cmds:
            try:
                self.get_output(cmd, output, encoding=encoding)
            except Exception:
                if stop_on_errors:
                    raise
        return output

    def _run_command(self, host, command, sudo=False, user=None,
                     shell=None, use_shell=True, use_pty=True,
                     **paramiko_kwargs):
        """Make SSHClient, run command on host"""
        self._make_ssh_client(host, **paramiko_kwargs)
        return self.host_clients[host].exec_command(
            command, sudo=sudo, user=user, shell=shell,
            use_shell=use_shell, use_pty=use_pty)

    def get_output(self, cmd, output, encoding='utf-8'):
        """Get output from command greenlet.

        `output` parameter is modified in-place.

        :param cmd: Command to get output from
        :type cmd: :py:class:`gevent.Greenlet`
        :param output: Dictionary containing
          :py:class:`pssh.output.HostOutput` values to be updated with output
          from cmd
        :type output: dict
        :rtype: None"""
        try:
            (channel, host, stdout, stderr, stdin) = cmd.get()
        except Exception as ex:
            try:
                host = ex.args[1]
            except IndexError:
                logger.error("Got exception with no host argument - "
                             "cannot update output data with %s", ex)
                raise ex
            self._update_host_output(
                output, host, None, None, None, None, None, cmd, exception=ex)
            raise
        stdout = self.host_clients[host].read_output_buffer(
            stdout, callback=self.get_exit_codes,
            callback_args=(output,),
            encoding=encoding)
        stderr = self.host_clients[host].read_output_buffer(
            stderr, prefix='\t[err]', callback=self.get_exit_codes,
            callback_args=(output,),
            encoding=encoding)
        self._update_host_output(output, host, self._get_exit_code(channel),
                                 channel, stdout, stderr, stdin, cmd)

    def join(self, output, consume_output=False):
        """Block until all remote commands in output have finished
        and retrieve exit codes

        :param output: Output of commands to join on
        :type output: dict as returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :param consume_output: Whether or not join should consume output
          buffers. Output buffers will be empty after ``join`` if set
          to ``True``. Must be set to ``True`` to allow host logger to log
          output on call to ``join``.
        :type consume_output: bool"""
        for host in output:
            output[host].cmd.join()
            if output[host].channel is not None:
                output[host].channel.recv_exit_status()
            if consume_output:
                for line in output[host].stdout:
                    pass
                for line in output[host].stderr:
                    pass
        self.get_exit_codes(output)

    def finished(self, output):
        """Check if commands have finished without blocking

        :param output: As returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: bool
        """
        for host in output:
            chan = output[host].channel
            if chan is not None and not chan.closed:
                return False
        return True

    def _get_exit_code(self, channel):
        """Get exit code from channel if ready"""
        if channel is None or not channel.exit_status_ready():
            return
        channel.close()
        return channel.recv_exit_status()

    def _make_ssh_client(self, host, **paramiko_kwargs):
        if host not in self.host_clients or self.host_clients[host] is None:
            _user, _port, _password, _pkey = self._get_host_config_values(host)
            self.host_clients[host] = SSHClient(
                host, user=_user, password=_password, port=_port, pkey=_pkey,
                forward_ssh_agent=self.forward_ssh_agent,
                num_retries=self.num_retries, timeout=self.timeout,
                proxy_host=self.proxy_host, proxy_port=self.proxy_port,
                proxy_user=self.proxy_user, proxy_password=self.proxy_password,
                proxy_pkey=self.proxy_pkey, allow_agent=self.allow_agent,
                agent=self.agent, channel_timeout=self.channel_timeout,
                **paramiko_kwargs)
