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


"""Package containing ParallelSSHClient class"""

import string  # noqa: E402
import random  # noqa: E402
import logging  # noqa: E402

import gevent.pool  # noqa: E402
import gevent.hub  # noqa: E402
gevent.hub.Hub.NOT_ERROR = (Exception,)

from .exceptions import HostArgumentException  # noqa: E402
from .constants import DEFAULT_RETRIES  # noqa: E402
from .output import HostOutput  # noqa: E402


logger = logging.getLogger(__name__)

try:
    xrange
except NameError:
    xrange = range


class BaseParallelSSHClient(object):

    def __init__(self, hosts, user=None, password=None, port=None, pkey=None,
                 allow_agent=True,
                 num_retries=DEFAULT_RETRIES,
                 timeout=120, pool_size=10,
                 host_config=None):
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
        :rtype: None

        `output` parameter is modified in-place and has the following structure

        ::

          {'myhost1':
                exit_code=exit code if ready else None
                channel=SSH channel of command
                stdout=<iterable>
                stderr=<iterable>
                cmd=<greenlet>
                exception=<exception object if applicable>
          }

        Stdout and stderr are also logged via the logger named ``host_logger``
        which can be enabled by calling ``enable_host_logger``

        **Example usage**:

        .. code-block:: python

          output = client.get_output()
          for host in output:
              for line in output[host].stdout:
                  print(line)
          <stdout>
          # Get exit code for a particular host's output after command
          # has finished
          self.get_exit_code(output[host])
          0

        """
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

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         suffix_separator='_'):
        raise NotImplementedError

    def _copy_remote_file(self, host, remote_file, local_file, recurse,
                          suffix_separator='_'):
        raise NotImplementedError

    def copy_file(self, local_file, remote_file, recurse=False):
        raise NotImplementedError

    def _copy_file(self, host, local_file, remote_file, recurse=False):
        raise NotImplementedError

    def _get_exit_code(self, channel):
        raise NotImplementedError

    def _make_ssh_client(self, host):
        raise NotImplementedError
