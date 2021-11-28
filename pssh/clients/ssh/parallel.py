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

from .single import SSHClient
from ..common import _validate_pkey_path, _validate_pkey
from ..base.parallel import BaseParallelSSHClient
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)


class ParallelSSHClient(BaseParallelSSHClient):
    """ssh-python based parallel client."""

    def __init__(self, hosts, user=None, password=None, port=22, pkey=None,
                 cert_file=None,
                 num_retries=DEFAULT_RETRIES, timeout=None, pool_size=100,
                 allow_agent=True, host_config=None, retry_delay=RETRY_DELAY,
                 forward_ssh_agent=False,
                 gssapi_auth=False,
                 gssapi_server_identity=None,
                 gssapi_client_identity=None,
                 gssapi_delegate_credentials=False,
                 identity_auth=True,
                 ipv6_only=False,
                 ):
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
          Bytes type input is used as private key data for authentication.
        :type pkey: str or bytes
        :param cert_file: Public key signed certificate file to use for
          authentication. The corresponding private key must also be provided
          via ``pkey`` parameter.
          For example ``pkey='id_rsa', cert_file='id_rsa-cert.pub'`` for RSA
          signed certificate.
          Path must be absolute or relative to user home directory.
        :type cert_file: str
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
        :type host_config: list(:py:class:`pssh.config.HostConfig`)
        :param allow_agent: (Optional) set to False to disable connecting to
          the system's SSH agent. Currently unused - always off.
        :type allow_agent: bool
        :param identity_auth: (Optional) set to False to disable attempting to
          authenticate with default identity files from
          `pssh.clients.base_ssh_client.BaseSSHClient.IDENTITIES`
        :type identity_auth: bool
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
        :param gssapi_server_identity: Set GSSAPI server identity.
        :type gssapi_server_identity: str
        :param gssapi_server_identity: Set GSSAPI client identity.
        :type gssapi_server_identity: str
        :param gssapi_delegate_credentials: Enable/disable server credentials
          delegation.
        :type gssapi_delegate_credentials: bool
        :param ipv6_only: Choose IPv6 addresses only if multiple are available
          for the host or raise NoIPv6AddressFoundError otherwise. Note this will
          disable connecting to an IPv4 address if an IP address is provided instead.
        :type ipv6_only: bool

        :raises: :py:class:`pssh.exceptions.PKeyFileError` on errors finding
          provided private key.
        """
        BaseParallelSSHClient.__init__(
            self, hosts, user=user, password=password, port=port, pkey=pkey,
            allow_agent=allow_agent, num_retries=num_retries,
            timeout=timeout, pool_size=pool_size,
            host_config=host_config, retry_delay=retry_delay,
            identity_auth=identity_auth,
            ipv6_only=ipv6_only,
        )
        self.pkey = _validate_pkey(pkey)
        self.cert_file = _validate_pkey_path(cert_file)
        self.forward_ssh_agent = forward_ssh_agent
        self.gssapi_auth = gssapi_auth
        self.gssapi_server_identity = gssapi_server_identity
        self.gssapi_client_identity = gssapi_client_identity
        self.gssapi_delegate_credentials = gssapi_delegate_credentials

    def run_command(self, command, sudo=False, user=None, stop_on_errors=True,
                    use_pty=False, host_args=None, shell=None,
                    encoding='utf-8', read_timeout=None,
                    ):
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
          emulation. Defaults to ``False``
        :type use_pty: bool
        :param host_args: (Optional) Format command string with per-host
          arguments in ``host_args``. ``host_args`` length must equal length of
          host list - :py:class:`pssh.exceptions.HostArgumentError` is
          raised otherwise
        :type host_args: tuple or list
        :param encoding: Encoding to use for command string and output. Must be valid
          `Python codec <https://docs.python.org/library/codecs.html>`_
        :type encoding: str
        :param read_timeout: (Optional) Timeout in seconds for reading from stdout
          or stderr. Defaults to `self.timeout`. Reading from stdout/stderr will
          raise :py:class:`pssh.exceptions.Timeout`
          after ``timeout`` number seconds if remote output is not ready.
        :type read_timeout: float
        :rtype: list(:py:class:`pssh.output.HostOutput`)

        :raises: :py:class:`pssh.exceptions.AuthenticationError` on
          authentication error
        :raises: :py:class:`pssh.exceptions.UnknownHostError` on DNS
          resolution error
        :raises: :py:class:`pssh.exceptions.ConnectionError` on error
          connecting
        :raises: :py:class:`pssh.exceptions.HostArgumentError` on number of
          host arguments not equal to number of hosts
        :raises: :py:class:`TypeError` on not enough host arguments for cmd
          string format
        :raises: :py:class:`KeyError` on no host argument key in arguments
          dict for cmd string format
        :raises: :py:class:`pssh.exceptions.ProxyError` on errors connecting
          to proxy if a proxy host has been set.
        :raises: :py:class:`pssh.exceptions.Timeout` on timeout starting command.
        :raises: Exceptions from :py:mod:`ssh.exceptions` for all other
          specific errors.
        """
        return BaseParallelSSHClient.run_command(
            self, command, stop_on_errors=stop_on_errors, host_args=host_args,
            user=user, shell=shell, sudo=sudo,
            encoding=encoding, use_pty=use_pty,
            read_timeout=read_timeout,
        )

    def _make_ssh_client(self, host_i, host):
        logger.debug("Make client request for host %s, (host_i, host) in clients: %s",
                     host, (host_i, host) in self._host_clients)
        if (host_i, host) not in self._host_clients \
           or self._host_clients[(host_i, host)] is None:
            _user, _port, _password, _pkey, _, _, _, _, _ = \
                self._get_host_config_values(host_i, host)
            if isinstance(self.pkey, str):
                with open(_pkey, 'rb') as fh:
                    _pkey_data = fh.read()
            else:
                _pkey_data = _pkey
            _client = SSHClient(
                host, user=_user, password=_password, port=_port,
                pkey=_pkey_data,
                cert_file=self.cert_file,
                num_retries=self.num_retries,
                timeout=self.timeout,
                allow_agent=self.allow_agent, retry_delay=self.retry_delay,
                gssapi_auth=self.gssapi_auth,
                gssapi_server_identity=self.gssapi_server_identity,
                gssapi_client_identity=self.gssapi_client_identity,
                gssapi_delegate_credentials=self.gssapi_delegate_credentials,
                identity_auth=self.identity_auth,
                ipv6_only=self.ipv6_only,
            )
            self._host_clients[(host_i, host)] = _client
            # TODO - Add forward agent functionality
            # forward_ssh_agent=self.forward_ssh_agent)
            return _client
        return self._host_clients[(host_i, host)]
