# This file is part of parallel-ssh.

# Copyright (C) 2014-2018 Panos Kittenis.

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
from gevent.lock import RLock

from .single import SSHClient
from ..native.common import _validate_pkey_path
from ..base_pssh import BaseParallelSSHClient
from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from ...exceptions import Timeout


logger = logging.getLogger(__name__)


class ParallelSSHClient(BaseParallelSSHClient):
    """ssh-python based parallel client."""

    def __init__(self, hosts, user=None, password=None, port=22, pkey=None,
                 num_retries=DEFAULT_RETRIES, timeout=None, pool_size=100,
                 allow_agent=True, host_config=None, retry_delay=RETRY_DELAY,
                 forward_ssh_agent=False):
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
        :param timeout: (Optional) Individual SSH client timeout setting in
          seconds passed on to each SSH client spawned by `ParallelSSHClient`.

          This controls timeout setting of socket operations used for SSH
          sessions *on a per session basis* meaning for each individual
          SSH session.

          Defaults to OS default - usually 60 seconds.

          Parallel functions like `run_command` and `join` have a cummulative
          timeout setting that is separate to and
          not affected by `self.timeout`.
        :type timeout: float
        :param pool_size: (Optional) Greenlet pool size. Controls
          concurrency, on how many hosts to execute tasks in parallel.
          Defaults to 100. Overhead in event
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
          Currently unused meaning always off.
        :type forward_ssh_agent: bool

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        BaseParallelSSHClient.__init__(
            self, hosts, user=user, password=password, port=port, pkey=pkey,
            allow_agent=allow_agent, num_retries=num_retries,
            timeout=timeout, pool_size=pool_size,
            host_config=host_config, retry_delay=retry_delay)
        self.pkey = _validate_pkey_path(pkey)
        self.forward_ssh_agent = forward_ssh_agent
        self._clients_lock = RLock()

    def run_command(self, command, sudo=False, user=None, stop_on_errors=True,
                    use_pty=False, host_args=None, shell=None,
                    encoding='utf-8', timeout=None, greenlet_timeout=None):
        """Run command on all hosts in parallel, honoring self.pool_size,
        and return output.

        This function will block until all commands have been received
        by remote servers and then return immediately.

        More explicitly, function will return after connection and
        authentication establishment in the case of on new connections and
        after execute
        commands have been accepted by successfully established SSH channels.

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
          hang indefinitely if remote server is unavailable.

          Use this setting
          to avoid blocking in such circumstances.
          Note that ``gevent.Timeout`` is a special class that inherits from
          ``BaseException`` and thus **can not be caught** by
          ``stop_on_errors=False``.
        :type greenlet_timeout: float
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
            greenlet_timeout=greenlet_timeout)


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
            if not channel.is_eof():
                raise Timeout(
                    "Timeout of %s sec(s) reached on host %s with command "
                    "still running", timeout, host)

    def _make_ssh_client(self, host_i, host):
        logger.debug(
            "Make client request for host %s, (host_i, host) in clients: %s",
            host, (host_i, host) in self._host_clients)
        with self._clients_lock:
            if (host_i, host) not in self._host_clients \
               or self._host_clients[(host_i, host)] is None:
                _user, _port, _password, _pkey = self._get_host_config_values(
                    host)
                _client = SSHClient(
                    host, user=_user, password=_password, port=_port,
                    pkey=_pkey, num_retries=self.num_retries,
                    timeout=self.timeout,
                    allow_agent=self.allow_agent, retry_delay=self.retry_delay)
                self.host_clients[host] = _client
                self._host_clients[(host_i, host)] = _client
                # TODO - Add forward agent functionality
                # forward_ssh_agent=self.forward_ssh_agent)
                return _client
        return self._host_clients[(host_i, host)]

    def finished(self, output):
        """Check if commands have finished without blocking

        :param output: As returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: bool
        """
        if isinstance(output, dict):
            for host_out in output.values():
                chan = host_out.channel
                if host_out.client and not host_out.client.finished(chan):
                    return False
        elif isinstance(output, list):
            for host_out in output:
                chan = host_out.channel
                if host_out.client and not host_out.client.finished(chan):
                    return False
        return True
