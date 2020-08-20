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

import string
import random
import logging

import gevent.pool

from warnings import warn
from gevent import joinall
from gevent.hub import Hub

from ..exceptions import HostArgumentException
from ..constants import DEFAULT_RETRIES, RETRY_DELAY
from ..output import HostOutput


Hub.NOT_ERROR = (Exception,)
logger = logging.getLogger(__name__)
_output_depr_notice = "run_command output will change to a list rather than " \
                      "dictionary in 2.0.0 - Please use return_list=True " \
                      "to avoid client code breaking on upgrading to 2.0.0"
_get_output_depr_notice = "get_output is scheduled to be removed in 2.0.0."

try:
    xrange
except NameError:
    xrange = range


class BaseParallelSSHClient(object):

    """Parallel client base class."""

    def __init__(self, hosts, user=None, password=None, port=None, pkey=None,
                 allow_agent=True,
                 num_retries=DEFAULT_RETRIES,
                 timeout=120, pool_size=10,
                 host_config=None, retry_delay=RETRY_DELAY):
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
        # To hold host clients
        self.host_clients = {}
        self._host_clients = {}
        self.host_config = host_config if host_config else {}
        self.retry_delay = retry_delay
        self.cmds = None

    def run_command(self, command, user=None, stop_on_errors=True,
                    host_args=None, use_pty=False, shell=None,
                    encoding='utf-8', return_list=False,
                    *args, **kwargs):
        greenlet_timeout = kwargs.pop('greenlet_timeout', None)
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
                raise HostArgumentException(
                    "Number of host arguments provided does not match "
                    "number of hosts ")
        else:
            cmds = [self.pool.spawn(
                self._run_command, host_i, host, command,
                user=user, encoding=encoding, use_pty=use_pty, shell=shell,
                *args, **kwargs)
                    for host_i, host in enumerate(self.hosts)]
        self.cmds = cmds
        joinall(cmds, raise_error=False, timeout=greenlet_timeout)
        return self._get_output_from_cmds(cmds, stop_on_errors=stop_on_errors,
                                          timeout=greenlet_timeout,
                                          return_list=return_list)

    def _get_output_from_cmds(self, cmds, stop_on_errors=False, timeout=None,
                              return_list=False):
        if not return_list:
            warn(_output_depr_notice)
            output = {}
            return self._get_output_dict(
                cmds, output, stop_on_errors=stop_on_errors,
                timeout=timeout)
        return [self._get_output_from_greenlet(cmd, timeout=timeout)
                for cmd in cmds]

    def _get_output_from_greenlet(self, cmd, timeout=None):
        try:
            (channel, host, stdout, stderr, stdin), _client = cmd.get(
                timeout=timeout)
        except Exception as ex:
            host = ex.host
            return HostOutput(host, cmd, None, None, None, None,
                              None, exception=ex)
        return HostOutput(host, cmd, channel, stdout, stderr, stdin, _client)

    def _get_output_dict(self, cmds, output, timeout=None,
                         stop_on_errors=False):
        for cmd in cmds:
            try:
                self.get_output(cmd, output, timeout=timeout)
            except Exception:
                if stop_on_errors:
                    raise
        return output

    def get_last_output(self, cmds=None, greenlet_timeout=None,
                        return_list=False):
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
        :param return_list: (Optional) Return a list of ``HostOutput`` objects
          instead of dictionary. ``run_command`` will return a list starting
          from 2.0.0 - enable this flag to avoid client code breaking on
          upgrading to 2.0.0.
        :type return_list: bool

        :rtype: dict or list
        """
        cmds = self.cmds if cmds is None else cmds
        if cmds is None:
            return
        return self._get_output_from_cmds(
            cmds, timeout=greenlet_timeout, return_list=return_list,
            stop_on_errors=False)

    def _get_host_config_values(self, host):
        _user = self.host_config.get(host, {}).get('user', self.user)
        _port = self.host_config.get(host, {}).get('port', self.port)
        _password = self.host_config.get(host, {}).get(
            'password', self.password)
        _pkey = self.host_config.get(host, {}).get('private_key', self.pkey)
        return _user, _port, _password, _pkey

    def _run_command(self, host_i, host, command, sudo=False, user=None,
                     shell=None, use_pty=False,
                     encoding='utf-8', timeout=None):
        """Make SSHClient if needed, run command on host"""
        try:
            _client = self._make_ssh_client(host_i, host)
            return _client.run_command(
                command, sudo=sudo, user=user, shell=shell,
                use_pty=use_pty, encoding=encoding, timeout=timeout), _client
        except Exception as ex:
            ex.host = host
            logger.error("Failed to run on host %s - %s", host, ex)
            raise ex

    def get_output(self, cmd, output, timeout=None):
        """Get output from command.

        :param output: Dictionary containing
          :py:class:`pssh.output.HostOutput` values to be updated with output
          from cmd
        :type output: dict
        :rtype: None
        """
        warn(_get_output_depr_notice)
        if not isinstance(output, dict):
            raise ValueError(
                "get_output is for the deprecated dictionary output only. "
                "To be removed in 2.0.0")
        try:
            (channel, host, stdout, stderr, stdin), _client = cmd.get(
                timeout=timeout)
        except Exception as ex:
            host = ex.host
            self._update_host_output(
                output, host, None, None, None, None, cmd, None, exception=ex)
            raise
        self._update_host_output(
            output, host, channel, stdout, stderr, stdin, cmd, _client)

    def _consume_output(self, stdout, stderr):
        for line in stdout:
            pass
        for line in stderr:
            pass

    def _update_host_output(self, output, host, channel, stdout,
                            stderr, stdin, cmd, client, exception=None):
        """Update host output with given data"""
        if host in output:
            new_host = "_".join([host,
                                 ''.join(random.choice(
                                     string.ascii_lowercase + string.digits)
                                     for _ in xrange(8))])
            logger.warning("Already have output for host %s - changing host "
                           "key for %s to %s", host, host, new_host)
            host = new_host
        output[host] = HostOutput(host, cmd, channel, stdout, stderr, stdin,
                                  client, exception=exception)

    def join(self, output, consume_output=False):
        raise NotImplementedError

    def finished(self, output):
        """Check if commands have finished without blocking

        :param output: As returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: bool
        """
        for host in output:
            chan = output[host].channel
            if chan is not None and not chan.eof():
                return False
        return True

    def get_exit_codes(self, output):
        """This function is now a no-op. Exit code is gathered
        on calling .exit_code on a ``HostOutput`` object.

        to be removed in 2.0.0
        """
        warn("get_exit_codes is deprecated and will be removed in 2.0.0")

    def get_exit_code(self, host_output):
        """This function is now a no-op. Exit code is gathered
        on calling .exit_code on a ``HostOutput`` object.

        to be removed in 2.0.0
        """
        warn("get_exit_code is deprecated and will be removed in 2.0.0")

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
          :py:class:`pssh.exceptions.HostArgumentException` is raised otherwise
        :type copy_args: tuple or list

        :rtype: List(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
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
                raise HostArgumentException(
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
          :py:class:`pssh.exceptions.HostArgumentException` is raised otherwise
        :type copy_args: tuple or list
        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands
        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`pssh.exceptions.HostArgumentException` on number of
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
                raise HostArgumentException(
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
