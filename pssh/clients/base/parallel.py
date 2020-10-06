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

"""Abstract parallel SSH client package"""

import logging

import gevent.pool

from gevent import joinall, spawn, Timeout as GTimeout
from gevent.hub import Hub

from ...constants import DEFAULT_RETRIES, RETRY_DELAY
from ...exceptions import HostArgumentError, Timeout
from ...output import HostOutput


Hub.NOT_ERROR = (Exception,)
logger = logging.getLogger(__name__)


class BaseParallelSSHClient(object):
    """Parallel client base class."""

    def __init__(self, hosts, user=None, password=None, port=None, pkey=None,
                 allow_agent=True,
                 num_retries=DEFAULT_RETRIES,
                 timeout=120, pool_size=10,
                 host_config=None, retry_delay=RETRY_DELAY,
                 identity_auth=True):
        if isinstance(hosts, str) or isinstance(hosts, bytes):
            raise TypeError(
                "Hosts must be list or other iterable, not string. "
                "For example: ['localhost'] not 'localhost'.")
        self.allow_agent = allow_agent
        self.pool_size = pool_size
        self.pool = gevent.pool.Pool(size=self.pool_size)
        self.hosts = hosts
        self.user = user
        self.password = password
        self.port = port
        self.pkey = pkey
        self.num_retries = num_retries
        self.timeout = timeout
        self._host_clients = {}
        self.host_config = host_config
        self.retry_delay = retry_delay
        self.cmds = None
        self.identity_auth = identity_auth
        self._check_host_config()

    def _check_host_config(self):
        if self.host_config is None:
            return
        host_len = 0
        try:
            host_len = len(self.hosts)
        except TypeError:
            # Generator
            return
        if host_len != len(self.host_config):
            raise ValueError(
                "Host config entries must match number of hosts if provided. "
                "Got %s host config entries from %s hosts" % (
                    len(self.host_config), host_len))

    def run_command(self, command, user=None, stop_on_errors=True,
                    host_args=None, use_pty=False, shell=None,
                    encoding='utf-8', return_list=True,
                    *args, **kwargs):
        if host_args:
            try:
                cmds = [self.pool.spawn(
                    self._run_command, host_i, host,
                    command % host_args[host_i],
                    user=user, encoding=encoding,
                    use_pty=use_pty, shell=shell,
                    *args, **kwargs)
                        for host_i, host in enumerate(self.hosts)]
            except IndexError:
                raise HostArgumentError(
                    "Number of host arguments provided does not match "
                    "number of hosts ")
        else:
            cmds = [self.pool.spawn(
                self._run_command, host_i, host, command,
                user=user, encoding=encoding, use_pty=use_pty, shell=shell,
                *args, **kwargs)
                    for host_i, host in enumerate(self.hosts)]
        self.cmds = cmds
        joinall(cmds, timeout=self.timeout)
        return self._get_output_from_cmds(cmds, raise_error=stop_on_errors,
                                          return_list=return_list)

    def _get_output_from_cmds(self, cmds, raise_error=False,
                              return_list=True):
        _cmds = [spawn(self._get_output_from_greenlet, cmd, raise_error=raise_error)
                 for cmd in cmds]
        finished = joinall(_cmds, raise_error=True)
        return [f.get() for f in finished]

    def _get_output_from_greenlet(self, cmd, raise_error=False):
        try:
            host_out = cmd.get()
            return host_out
        except (GTimeout, Exception) as ex:
            host = ex.host if hasattr(ex, 'host') else None
            if isinstance(ex, GTimeout):
                ex = Timeout()
            if raise_error:
                raise ex
            return HostOutput(host, None, None, None, None,
                              None, exception=ex)

    def get_last_output(self, cmds=None, timeout=None,
                        return_list=True):
        """Get output for last commands executed by ``run_command``

        :param cmds: Commands to get output for. Defaults to ``client.cmds``
        :type cmds: list(:py:class:`gevent.Greenlet`)
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
        :param return_list: No-op - list of ``HostOutput`` always returned.
          Parameter kept for backwards compatibility - to be removed in future
          releases.
        :type return_list: bool

        :rtype: dict or list
        """
        cmds = self.cmds if cmds is None else cmds
        if cmds is None:
            return
        return self._get_output_from_cmds(
            cmds, return_list=return_list,
            raise_error=False)

    def reset_output_generators(self, host_out, timeout=None,
                                client=None, channel=None,
                                encoding='utf-8'):
        """Reset output generators for host output.

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

    def _get_host_config_values(self, host_i, host):
        if self.host_config is None:
            return self.user, self.port, self.password, self.pkey
        elif isinstance(self.host_config, list):
            _user = self.host_config[host_i].user
            _port = self.host_config[host_i].port
            _password = self.host_config[host_i].password
            _pkey = self.host_config[host_i].private_key
            return _user, _port, _password, _pkey
        elif isinstance(self.host_config, dict):
            _user = self.host_config.get(host, {}).get('user', self.user)
            _port = self.host_config.get(host, {}).get('port', self.port)
            _password = self.host_config.get(host, {}).get(
                'password', self.password)
            _pkey = self.host_config.get(host, {}).get('private_key', self.pkey)
            return _user, _port, _password, _pkey

    def _run_command(self, host_i, host, command, sudo=False, user=None,
                     shell=None, use_pty=False,
                     encoding='utf-8', read_timeout=None):
        """Make SSHClient if needed, run command on host"""
        logger.debug("_run_command with read timeout %s", read_timeout)
        try:
            _client = self._make_ssh_client(host_i, host)
            host_out = _client.run_command(
                command, sudo=sudo, user=user, shell=shell,
                use_pty=use_pty, encoding=encoding, read_timeout=read_timeout)
            return host_out
        except (GTimeout, Exception) as ex:
            host = ex.host if hasattr(ex, 'host') else None
            logger.error("Failed to run on host %s - %s", host, ex)
            raise ex

    def _consume_output(self, stdout, stderr):
        for line in stdout:
            pass
        for line in stderr:
            pass

    def join(self, output, consume_output=False, timeout=None,
             encoding='utf-8'):
        """Wait until all remote commands in output have finished.
        Does *not* block other commands from running in parallel.

        :param output: Output of commands to join on
        :type output: `HostOutput` objects
        :param consume_output: Whether or not join should consume output
          buffers. Output buffers will be empty after ``join`` if set
          to ``True``. Must be set to ``True`` to allow host logger to log
          output on call to ``join`` when host logger has been enabled.
        :type consume_output: bool
        :param timeout: Timeout in seconds if **all** remote commands are not
          yet finished. Note that use of timeout forces ``consume_output=True``
          otherwise the channel output pending to be consumed always results
          in the channel not being finished.
          This function's timeout is for all commands in total and will therefor
          be affected by pool size and total number of concurrent commands in
          self.pool.
          Since self.timeout is passed onto each individual SSH session it is
          **not** used for any parallel functions like `run_command` or `join`.
        :type timeout: int
        :param encoding: Encoding to use for output. Must be valid
          `Python codec <https://docs.python.org/library/codecs.html>`_
        :type encoding: str

        :raises: :py:class:`pssh.exceptions.Timeout` on timeout requested and
          reached with commands still running.

        :rtype: ``None``"""
        if not isinstance(output, list):
            raise ValueError("Unexpected output object type")
        cmds = [self.pool.spawn(self._join, host_out, timeout=timeout,
                                consume_output=consume_output, encoding=encoding)
                for host_i, host_out in enumerate(output)]
        # Errors raised by self._join should be propagated.
        finished_cmds = joinall(cmds, raise_error=True, timeout=timeout)
        if timeout is None:
            return
        unfinished_cmds = set.difference(set(cmds), set(finished_cmds))
        if unfinished_cmds:
            finished_output = self.get_last_output(cmds=finished_cmds)
            unfinished_output = list(set.difference(set(output), set(finished_output)))
            raise Timeout("Timeout of %s sec(s) reached with commands "
                          "still running", timeout, finished_output, unfinished_output)

    def _join(self, host_out, consume_output=False, timeout=None,
              encoding="utf-8"):
        if host_out is None:
            return
        channel = host_out.channel
        client = host_out.client
        if client is None:
            return
        stdout, stderr = self.reset_output_generators(
            host_out, channel=channel, timeout=timeout,
            encoding=encoding)
        client.wait_finished(channel, timeout=timeout)
        if consume_output:
            self._consume_output(stdout, stderr)
        return host_out

    def finished(self, output):
        """Check if commands have finished without blocking

        :param output: As returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: bool
        """
        for host_out in output:
            chan = host_out.channel
            if host_out.client and not host_out.client.finished(chan):
                return False
        return True

    def copy_file(self, local_file, remote_file, recurse=False, copy_args=None):
        """Copy local file to remote file in parallel

        This function returns a list of greenlets which can be
        `join`-ed on to wait for completion.

        :py:func:`gevent.joinall` function may be used to join on all greenlets
        and will also raise exceptions from them if called with
        ``raise_error=True`` - default is `False`.

        Alternatively call `.get` on each greenlet to raise any exceptions from
        it.

        Exceptions listed here are raised when
        either ``gevent.joinall(<greenlets>, raise_error=True)`` is called
        or ``.get`` is called on each greenlet, not this function itself.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool
        :param copy_args: (Optional) format local_file and remote_file strings
          with per-host arguments in ``copy_args``. ``copy_args`` length must
          equal length of host list -
          :py:class:`pssh.exceptions.HostArgumentError` is raised otherwise
        :type copy_args: tuple or list

        :rtype: List(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`pssh.exceptions.HostArgumentError` on number of
          per-host copy arguments not equal to number of hosts
        :raises: :py:class:`IOError` on I/O errors writing files
        :raises: :py:class:`OSError` on OS errors like permission denied

        .. note ::

          Remote directories in `remote_file` that do not exist will be
          created as long as permissions allow.

        """
        if copy_args:
            try:
                return [self.pool.spawn(self._copy_file, host_i, host,
                                        local_file % copy_args[host_i],
                                        remote_file % copy_args[host_i],
                                        {'recurse': recurse})
                        for host_i, host in enumerate(self.hosts)]
            except IndexError:
                raise HostArgumentError(
                    "Number of per-host copy arguments provided does not match "
                    "number of hosts")
        else:
            return [self.pool.spawn(self._copy_file, host_i, host, local_file,
                                    remote_file, {'recurse': recurse})
                    for host_i, host in enumerate(self.hosts)]

    def _copy_file(self, host_i, host, local_file, remote_file, recurse=False):
        """Make sftp client, copy file"""
        try:
            self._make_ssh_client(host_i, host)
            return self._host_clients[(host_i, host)].copy_file(
                local_file, remote_file, recurse=recurse)
        except Exception as ex:
            ex.host = host
            raise ex

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         suffix_separator='_', copy_args=None, **kwargs):
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
          host ``myhost``. ``suffix_separator`` has no meaning if
          ``copy_args`` is provided
        :type suffix_separator: str
        :param copy_args: (Optional) Format remote_file and local_file strings
          with per-host arguments in ``copy_args``. ``copy_args`` length must
          equal length of host list -
          :py:class:`pssh.exceptions.HostArgumentError` is raised otherwise
        :type copy_args: tuple or list
        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands
        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`pssh.exceptions.HostArgumentError` on number of
          per-host copy arguments not equal to number of hosts
        :raises: :py:class:`IOError` on I/O errors writing files
        :raises: :py:class:`OSError` on OS errors like permission denied

        .. note ::
          Local directories in ``local_file`` that do not exist will be
          created as long as permissions allow.

        .. note ::
          File names will be de-duplicated by appending the hostname to the
          filepath separated by ``suffix_separator``.

        """
        if copy_args:
            try:
                return [self.pool.spawn(
                    self._copy_remote_file, host_i, host,
                    remote_file % copy_args[host_i],
                    local_file % copy_args[host_i], recurse=recurse, **kwargs)
                    for host_i, host in enumerate(self.hosts)]
            except IndexError:
                raise HostArgumentError(
                    "Number of per-host copy arguments provided does not match "
                    "number of hosts")
        else:
            return [self.pool.spawn(
                self._copy_remote_file, host_i, host, remote_file,
                suffix_separator.join([local_file, host]), recurse, **kwargs)
                    for host_i, host in enumerate(self.hosts)]

    def _copy_remote_file(self, host_i, host, remote_file, local_file, recurse,
                          **kwargs):
        """Make sftp client, copy file to local"""
        try:
            self._make_ssh_client(host_i, host)
            return self._host_clients[(host_i, host)].copy_remote_file(
                remote_file, local_file, recurse=recurse, **kwargs)
        except Exception as ex:
            ex.host = host
            raise ex

    def _handle_greenlet_exc(self, func, host, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            ex.host = host
            raise ex

    def _make_ssh_client(self, host_i, host):
        raise NotImplementedError
