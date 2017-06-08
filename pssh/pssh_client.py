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

import sys
if 'threading' in sys.modules:
    del sys.modules['threading']
from gevent import monkey  # noqa: E402
monkey.patch_all()
import string  # noqa: E402
import random  # noqa: E402
import logging  # noqa: E402

import gevent.pool  # noqa: E402
import gevent.hub  # noqa: E402
gevent.hub.Hub.NOT_ERROR = (Exception,)

from .exceptions import HostArgumentException  # noqa: E402
from .constants import DEFAULT_RETRIES  # noqa: E402
from .ssh_client import SSHClient  # noqa: E402
from .output import HostOutput  # noqa: E402


logger = logging.getLogger('pssh')

try:
    xrange
except NameError:
    xrange = range


class ParallelSSHClient(object):
    """Uses :py:class:`pssh.ssh_client.SSHClient`, performs tasks over SSH on
    multiple hosts in parallel.

    Connections to hosts are established in parallel when ``run_command`` is
    called, therefor any connection and/or authentication exceptions will
    happen on the call to ``run_command`` and need to be handled there.
    """

    def __init__(self, hosts, user=None, password=None, port=None, pkey=None,
                 forward_ssh_agent=True, num_retries=DEFAULT_RETRIES,
                 timeout=120, pool_size=10, proxy_host=None, proxy_port=22,
                 proxy_user=None, proxy_password=None, proxy_pkey=None,
                 agent=None, allow_agent=True, host_config=None,
                 channel_timeout=None):
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
        :type allow_agent: bool

        **Example Usage**

        .. code-block:: python

          from __future__ import print_function
          from pprint import pprint

          from pssh.pssh_client import ParallelSSHClient
          from pssh.exceptions import AuthenticationException, \\
              UnknownHostException, ConnectionErrorException

          client = ParallelSSHClient(['myhost1', 'myhost2'])
          try:
              output = client.run_command('ls -ltrh /tmp/aasdfasdf', sudo=True)
          except (AuthenticationException, UnknownHostException,
                  ConnectionErrorException):
              pass

        Commands have started executing at this point.
        Exit code(s) will not be available immediately.

        .. code-block:: python

          pprint(output)
            {'myhost1':
                  host=myhost1
                  exit_code=None
                  cmd=<Greenlet>
                  channel=<channel>
                  stdout=<generator>
                  stderr=<generator>
                  stdin=<channel>
                  exception=None
             'myhost2':
                  host=myhost2
                  exit_code=None
                  cmd=<Greenlet>
                  channel=<channel>
                  stdout=<generator>
                  stderr=<generator>
                  stdin=<channel>
                  exception=None
            }

        :Enabling host logger:

        There is a host logger in parallel-ssh that can be enabled to show
        stdout from remote commands on hosts as it comes in.

        This allows for stdout to be automatically logged without having to
        print it serially per host. :mod:`pssh.utils.host_logger` is a standard
        library logger and may be configured to log to anywhere else.

        For host logger to log output, ``join`` must be called with
        ``consume_output=True``

        .. code-block:: python

          import pssh.utils
          pssh.utils.enable_host_logger()

          output = client.run_command('ls -ltrh')
          client.join(output, consume_output=True)
          [myhost1]     drwxrwxr-x 6 user group 4.0K Jan 1 HH:MM x
          [myhost2]     drwxrwxr-x 6 user group 4.0K Jan 1 HH:MM x

        Retrieve exit codes after commands have finished as below.

        ``exit_code`` in ``output`` will be ``None`` immediately after call to
        ``run_command``.

        `parallel-ssh` starts commands asynchronously to enable starting
        multiple commands in parallel without blocking.

        Because of this, exit codes will not be immediately available even for
        commands that exit immediately.

        :Waiting for command completion:

        At least one of

        * Iterating over stdout/stderr to completion
        * Calling ``client.join(output)``

        is necessary to cause ``parallel-ssh`` to wait for commands to finish
        and be able to gather exit codes.

        An individual command's exit code can be gathered by
        ``get_exit_code(host_output)``

        .. seealso:: :py:func:`get_exit_code`, :py:func:`get_output`

        .. note ::

          **Joining on client's gevent pool**

          ``client.pool.join()`` only blocks *until greenlets have been spawned*
          which will be immediately as long as pool is not full.

        :Checking command completion:

        To check if commands have finished *without blocking* use

        .. code-block:: python

          client.finished(output)
          False

        which returns ``True`` if and only if all commands in output have
        finished.

        For individual commands the status of channel can be checked

        .. code-block:: python

          output[host].channel.closed
          False

        which returns ``True`` if command has finished.

        Either iterating over stdout/stderr or ``client.join(output)`` will
        cause exit codes to become available in output without explicitly
        calling ``get_exit_codes``.

        Use ``client.join(output)`` to block until all commands have finished
        and gather exit codes at same time.

        In versions prior to ``1.0.0`` only, ``client.join`` would consume
        output.

        **Exit code retrieval**

        ``get_exit_codes`` is not a blocking function and will not wait for
        commands to finish.

        ``output`` parameter is modified in-place.

        .. code-block:: python

            client.get_exit_codes(output)
            for host in output:
                print(output[host].exit_code)
            0
            0

        **Stdout from each host**

        .. code-block:: python

          for host in output:
              for line in output[host].stdout:
                  print(line)
          ls: cannot access /tmp/aasdfasdf: No such file or directory
          ls: cannot access /tmp/aasdfasdf: No such file or directory

        **Example with specified private key**

        .. code-block:: python

          from pssh.utils import load_private_key
          client_key = load_private_key('user.key')
          client = ParallelSSHClient(['myhost1', 'myhost2'], pkey=client_key)

        **Multiple commands**

        .. code-block:: python

          for cmd in ['uname', 'whoami']:
              client.run_command(cmd)

        **Per-Host configuration**

        Per host configuration can be provided for any or all of user, password
        port and private key. Private key value is a
        :py:class:`paramiko.pkey.PKey` object as returned by
        :py:func:`pssh.utils.load_private_key`.

        :py:func:`pssh.utils.load_private_key` accepts both file names and
        file-like objects and will attempt to load all available key types,
        returning ``None`` if they all fail.

        .. code-block:: python

          from pssh.utils import load_private_key

          host_config = { 'host1' : {'user': 'user1', 'password': 'pass',
                                     'port': 2222,
                                     'private_key': load_private_key(
                                         'my_key.pem')},
                          'host2' : {'user': 'user2', 'password': 'pass',
                                     'port': 2223,
                                     'private_key': load_private_key(
                                         open('my_other_key.pem'))},
                          }
          hosts = host_config.keys()

          client = ParallelSSHClient(hosts, host_config=host_config)
          client.run_command('uname')
          <..>

        .. note ::

          **Connection persistence**

          Connections to hosts will remain established for the duration of the
          object's life. To close them, just `del` or reuse the object reference

          .. code-block:: python

            client = ParallelSSHClient(['localhost'])
            output = client.run_command('ls')

          :netstat: ``tcp  0  0 127.0.0.1:53054    127.0.0.1:22    ESTABLISHED``

          Connection remains active after commands have finished executing. Any
          additional commands will reuse the same connection.

          .. code-block:: python

            del client

          Connection is terminated.
        """
        self.pool_size = pool_size
        self.pool = gevent.pool.Pool(size=self.pool_size)
        self.hosts = hosts
        self.user = user
        self.password = password
        self.forward_ssh_agent = forward_ssh_agent
        self.port = port
        self.pkey = pkey
        self.num_retries = num_retries
        self.timeout = timeout
        self.proxy_host, self.proxy_port, self.proxy_user, \
            self.proxy_password, self.proxy_pkey = proxy_host, proxy_port, \
            proxy_user, proxy_password, proxy_pkey
        # To hold host clients
        self.host_clients = {}
        self.agent = agent
        self.allow_agent = allow_agent
        self.host_config = host_config if host_config else {}
        self.channel_timeout = channel_timeout

    def run_command(self, command, sudo=False, user=None, stop_on_errors=True,
                    shell=None, use_shell=True, use_pty=True, host_args=None,
                    encoding='utf-8'):
        """Run command on all hosts in parallel, honoring self.pool_size,
        and return output buffers.

        This function will block until all commands have been *sent* to remote
        servers and then return immediately

        More explicitly, function will return after connection and
        authentication establishment and after commands have been sent to
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
          dict for cmd string format

        **Example Usage**

        :Simple run command:

        .. code-block:: python

          output = client.run_command('ls -ltrh')

        :Print stdout for each command:

        .. code-block:: python

          from __future__ import print_function

          for host in output:
              for line in output[host].stdout:
                  print(line)

        :Get exit codes after command has finished:

        .. code-block:: python

          from __future__ import print_function

          client.get_exit_codes(output)
          for host in output:
              print(output[host].exit_code)
          0
          0

        :Wait for completion, print exit codes:

        .. code-block:: python

          client.join(output)
          print(output[host].exit_code)
          0
          for line in output[host].stdout:
              print(line)

        :Run with sudo:

        .. code-block:: python

          output = client.run_command('ls -ltrh', sudo=True)

        :Capture stdout:

        .. warning::

          This will store the entirety of stdout
          into memory and may exhaust available memory if command output is
          large enough.

        Iterating over stdout/stderr to completion by definition implies
        blocking until command has finished. To only log output as it comes in
        without blocking the host logger can be enabled - see
        `Enabling Host Logger` above.

        .. code-block:: python

          from __future__ import print_function

          for host in output:
              stdout = list(output[host].stdout)
              print("Complete stdout for host %s is %s" % (host, stdout,))

        :Command with per-host arguments:

        ``host_args`` keyword parameter can be used to provide arguments to use
        to format the command string.

        Number of ``host_args`` should be at least as many as number of hosts.

        Any string format specification characters may be used in command
        string.

        :Examples:

        .. code-block:: python

          # Tuple
          #
          # First host in hosts list will use cmd 'host1_cmd',
          # second host 'host2_cmd' and so on
          output = client.run_command('%s', host_args=('host1_cmd',
                                                       'host2_cmd',
                                                       'host3_cmd',))

          # Multiple arguments
          #
          output = client.run_command('%s %s',
                                      host_args=(('host1_cmd1', 'host1_cmd2'),
                                                 ('host2_cmd1', 'host2_cmd2'),
                                                 ('host3_cmd1', 'host3_cmd2'),))

          # List of dict
          #
          # First host in host list will use cmd 'host-index-0',
          # second host 'host-index-1' and so on
          output = client.run_command(
            '%(cmd)s', host_args=[{'cmd': 'host-index-%s' % (i,))
                                  for i in range(len(client.hosts))])

        :Expression as host list:

        Any type of iterator may be used as host list, including generator and
        list comprehension expressions.

        .. code-block:: python

          hosts = ['dc1.myhost1', 'dc2.myhost2']
          # List comprehension
          client = ParallelSSHClient([h for h in hosts if h.find('dc1')])
          # Generator
          client = ParallelSSHClient((h for h in hosts if h.find('dc1')))
          # Filter
          client = ParallelSSHClient(filter(lambda h: h.find('dc1'), hosts))
          client.run_command(<..>)

        .. note ::

          Since generators by design only iterate over a sequence once then
          stop, ``client.hosts`` should be re-assigned after each call to
          ``run_command`` when using generators as target of `client.hosts`.

        :Overriding host list:

        Host list can be modified in place. Call to `run_command` will create
        new connections as necessary and output will only contain output for
        the hosts ``run_command`` executed on.

        .. code-block:: python

          client.hosts = ['otherhost']
          print(client.run_command('exit 0'))
          {'otherhost': exit_code=None, <..>}

        :Run multiple commands in parallel:

        This short example demonstrates running multiple long running commands
        in parallel on the same host, how long it takes for all commands to
        start, blocking until they complete and how long it takes for all
        commands to complete.

        See examples directory for complete script. ::

          output = []
          host = 'localhost'

          # Run 10 five second sleeps
          cmds = ['sleep 5' for _ in xrange(10)]
          start = datetime.datetime.now()
          for cmd in cmds:
              output.append(client.run_command(cmd, stop_on_errors=False))
          end = datetime.datetime.now()
          print("Started %s commands in %s" % (len(cmds), end-start,))
          start = datetime.datetime.now()
          for _output in output:
              for line in _output[host].stdout:
                  print(line)
          end = datetime.datetime.now()
          print("All commands finished in %s" % (end-start,))

        *Output*

        ::

          Started 10 commands in 0:00:00.428629
          All commands finished in 0:00:05.014757

        :Output format:

        ::

          {'myhost1':
                host=myhost1
                exit_code=exit code if ready else None
                channel=SSH channel of command
                stdout=<iterable>
                stderr=<iterable>
                stdin=<file-like writable channel>
                cmd=<greenlet>
                exception=None}

        :Do not stop on errors, return per-host exceptions in output:

        .. code-block:: python

          output = client.run_command('ls -ltrh', stop_on_errors=False)
          client.join(output)
          print(output)

        .. code-block:: python

          {'myhost1':
                host=myhost1
                exit_code=None
                channel=None
                stdout=None
                stderr=None
                cmd=None
                exception=ConnectionErrorException(
                            "Error connecting to host '%s:%s' - %s - "
                            "retry %s/%s",
                             host, port, 'Connection refused', 3, 3)}

        :Using stdin:

        .. code-block:: python

          output = client.run_command('read')
          stdin = output['localhost'].stdin
          stdin.write("writing to stdin\\n")
          stdin.flush()
          for line in output['localhost'].stdout:
              print(line)

          writing to stdin

        """
        output = {}
        if host_args:
            try:
                cmds = [self.pool.spawn(self._exec_command, host,
                                        command % host_args[host_i],
                                        sudo=sudo, user=user, shell=shell,
                                        use_shell=use_shell, use_pty=use_pty)
                        for host_i, host in enumerate(self.hosts)]
            except IndexError:
                raise HostArgumentException(
                    "Number of host arguments provided does not match "
                    "number of hosts ")
        else:
            cmds = [self.pool.spawn(
                self._exec_command, host, command,
                sudo=sudo, user=user, shell=shell,
                use_shell=use_shell, use_pty=use_pty)
                for host in self.hosts]
        for cmd in cmds:
            try:
                self.get_output(cmd, output, encoding=encoding)
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

    def _exec_command(self, host, command, sudo=False, user=None,
                      shell=None, use_shell=True, use_pty=True):
        """Make SSHClient, run command on host"""
        if host not in self.host_clients or self.host_clients[host] is None:
            _user, _port, _password, _pkey = self._get_host_config_values(host)
            _user = user if user else _user
            self.host_clients[host] = SSHClient(
                host, user=_user, password=_password, port=_port, pkey=_pkey,
                forward_ssh_agent=self.forward_ssh_agent,
                num_retries=self.num_retries, timeout=self.timeout,
                proxy_host=self.proxy_host, proxy_port=self.proxy_port,
                proxy_user=self.proxy_user, proxy_password=self.proxy_password,
                proxy_pkey=self.proxy_pkey, allow_agent=self.allow_agent,
                agent=self.agent, channel_timeout=self.channel_timeout)
        return self.host_clients[host].exec_command(
            command, sudo=sudo, user=user, shell=shell,
            use_shell=use_shell, use_pty=use_pty)

    def get_output(self, cmd, output, encoding='utf-8'):
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
            exc = sys.exc_info()
            try:
                host = ex.args[1]
            except IndexError as _ex:
                logger.error("Got exception with no host argument - "
                             "cannot update output data with %s", _ex)
                raise exc[1]
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
                                  exit_code=exit_code,
                                  exception=exception)

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
        :type consume_output: bool

        :Enabling host logger:

        .. code-block:: python

          from pssh.utils import enable_host_logger
          enable_host_logger()
          output = client.run_command(<..>)
          client.join(output, consume_output=True)

          # Output buffers now empty
          len(list(output[client.hosts[0]].stdout)) == 0

        With ``consume_output=True``, host logger logs output.

        .. code-block:: python

          [my_host1] <..>

        With ``consume_output=False``, the default, iterating over output is
        needed for host logger to log anything.

        .. code-block:: python

          output = client.run_command(<..>)
          client.join(output, consume_output=False)
          for host, host_out in output.items():
              for line in host_out.stdout:
                  pass

        .. code-block:: python

          [my_host1] <..>
        """
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
        if 'channel' not in host_output:
            logger.error("%s does not look like host output..", host_output,)
            return
        channel = host_output.channel
        return self._get_exit_code(channel)

    def _get_exit_code(self, channel):
        """Get exit code from channel if ready"""
        if channel is None or not channel.exit_status_ready():
            return
        channel.close()
        return channel.recv_exit_status()

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
                         suffix_separator='_'):
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
            local_file, recurse, suffix_separator=suffix_separator)
            for host in self.hosts]

    def _copy_remote_file(self, host, remote_file, local_file, recurse,
                          suffix_separator='_'):
        """Make sftp client, copy file to local"""
        file_w_suffix = suffix_separator.join([local_file, host])
        self._make_ssh_client(host)
        return self.host_clients[host].copy_remote_file(
                remote_file, file_w_suffix, recurse=recurse)

    def _make_ssh_client(self, host):
        if host not in self.host_clients or self.host_clients[host] is None:
            _user, _port, _password, _pkey = self._get_host_config_values(host)
            self.host_clients[host] = SSHClient(
                host, user=_user, password=_password, port=_port, pkey=_pkey,
                forward_ssh_agent=self.forward_ssh_agent,
                num_retries=self.num_retries,
                timeout=self.timeout,
                proxy_host=self.proxy_host,
                proxy_port=self.proxy_port,
                agent=self.agent,
                channel_timeout=self.channel_timeout)
