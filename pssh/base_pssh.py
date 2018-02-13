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

"""Abstract parallel SSH client package"""

import string
import random
import logging

import gevent.pool
from gevent.hub import Hub

from .exceptions import HostArgumentException
from .constants import DEFAULT_RETRIES, RETRY_DELAY
from .output import HostOutput


Hub.NOT_ERROR = (Exception,)
logger = logging.getLogger(__name__)

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
        self.host_config = host_config if host_config else {}
        self.retry_delay = retry_delay
        self.cmds = None

    def run_command(self, command, user=None, stop_on_errors=True,
                    host_args=None, use_pty=False, shell=None,
                    encoding='utf-8',
                    *args, **kwargs):
        output = {}
        if host_args:
            try:
                cmds = [self.pool.spawn(self._run_command, host,
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
                self._run_command, host, command,
                user=user, encoding=encoding, use_pty=use_pty, shell=shell,
                *args, **kwargs)
                    for host in self.hosts]
        for cmd in cmds:
            try:
                self.get_output(cmd, output)
            except Exception:
                if stop_on_errors:
                    raise
        self.cmds = cmds
        return output

    def get_last_output(self, cmds=None):
        """Get output for last commands executed by ``run_command``

        :param cmds: Commands to get output for. Defaults to ``client.cmds``
        :type cmds: list(:py:class:`gevent.Greenlet`)

        :rtype: dict
        """
        cmds = self.cmds if cmds is None else cmds
        if cmds is None:
            return
        output = {}
        for cmd in self.cmds:
            self.get_output(cmd, output)
        return output

    def _get_host_config_values(self, host):
        _user = self.host_config.get(host, {}).get('user', self.user)
        _port = self.host_config.get(host, {}).get('port', self.port)
        _password = self.host_config.get(host, {}).get(
            'password', self.password)
        _pkey = self.host_config.get(host, {}).get('private_key', self.pkey)
        return _user, _port, _password, _pkey

    def _run_command(self, host, command, *args, **kwargs):
        raise NotImplementedError

    def get_output(self, cmd, output):
        """Get output from command.

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
        self._update_host_output(output, host, self._get_exit_code(channel),
                                 channel, stdout, stderr, stdin, cmd)

    def _update_host_output(self, output, host, exit_code, channel, stdout,
                            stderr, stdin, cmd, exception=None):
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
                                  exit_code=exit_code, exception=exception)

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
        """Get exit code for all hosts in output *if available*.
        Output parameter is modified in-place.

        :param output: As returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: None
        """
        for host in output:
            if output[host] is None:
                continue
            output[host].exit_code = self.get_exit_code(output[host])

    def get_exit_code(self, host_output):
        """Get exit code from host output *if available*.

        :param host_output: Per host output as returned by
          :py:func:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: int or None if exit code not ready"""
        if not hasattr(host_output, 'channel'):
            logger.error("%s does not look like host output..", host_output,)
            return
        return self._get_exit_code(host_output.channel)

    def copy_file(self, local_file, remote_file, recurse=False):
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
        :rtype: List(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`IOError` on I/O errors writing files
        :raises: :py:class:`OSError` on OS errors like permission denied

        .. note ::

          Remote directories in `remote_file` that do not exist will be
          created as long as permissions allow.

        """
        return [self.pool.spawn(self._copy_file, host, local_file, remote_file,
                                {'recurse': recurse})
                for host in self.hosts]

    def _copy_file(self, host, local_file, remote_file, recurse=False):
        """Make sftp client, copy file"""
        self._make_ssh_client(host)
        return self.host_clients[host].copy_file(local_file, remote_file,
                                                 recurse=recurse)

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         suffix_separator='_', **kwargs):
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
        :rtype: list(:py:class:`gevent.Greenlet`) of greenlets for remote copy
          commands

        :raises: :py:class:`ValueError` when a directory is supplied to
          local_file and recurse is not set
        :raises: :py:class:`IOError` on I/O errors writing files
        :raises: :py:class:`OSError` on OS errors like permission denied

        .. note ::
          Local directories in `local_file` that do not exist will be
          created as long as permissions allow.

        .. note ::
          File names will be de-duplicated by appending the hostname to the
          filepath separated by ``suffix_separator``.

        """
        return [self.pool.spawn(
            self._copy_remote_file, host, remote_file,
            local_file, recurse, suffix_separator=suffix_separator,
            **kwargs)
            for host in self.hosts]

    def _copy_remote_file(self, host, remote_file, local_file, recurse,
                          suffix_separator='_', **kwargs):
        """Make sftp client, copy file to local"""
        file_w_suffix = suffix_separator.join([local_file, host])
        self._make_ssh_client(host)
        return self.host_clients[host].copy_remote_file(
            remote_file, file_w_suffix, recurse=recurse,
            **kwargs)
