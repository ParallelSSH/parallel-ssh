# This file is part of parallel-ssh.

# Copyright (C) 2014- Panos Kittenis

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


"""Package containing ParallelSSHClient class."""

import sys
if 'threading' in sys.modules:
    del sys.modules['threading']
from gevent import monkey
monkey.patch_all()
import logging
import gevent.pool
import gevent.hub
gevent.hub.Hub.NOT_ERROR = (Exception,)
import warnings
import string
import random
from .constants import DEFAULT_RETRIES
from .ssh_client import SSHClient


logger = logging.getLogger('pssh')


class ParallelSSHClient(object):
    """Uses :mod:`pssh.ssh_client.SSHClient`, performs tasks over SSH on multiple hosts in \
    parallel.
    
    Connections to hosts are established in parallel when ``run_command`` is called,
    therefor any connection and/or authentication exceptions will happen on the
    call to ``run_command`` and need to be caught.
    """
    
    def __init__(self, hosts,
                 user=None, password=None, port=None, pkey=None,
                 forward_ssh_agent=True, num_retries=DEFAULT_RETRIES, timeout=120,
                 pool_size=10, proxy_host=None, proxy_port=22,
                 agent=None, allow_agent=True, host_config=None, channel_timeout=None):
        """
        :param hosts: Hosts to connect to
        :type hosts: list(str)
        :param user: (Optional) User to login as. Defaults to logged in user or \
        user from ~/.ssh/config or /etc/ssh/ssh_config if set
        :type user: str
        :param password: (Optional) Password to use for login. Defaults to \
        no password
        :type password: str
        :param port: (Optional) Port number to use for SSH connection. Defaults \
        to None which uses SSH default
        :type port: int
        :param pkey: (Optional) Client's private key to be used to connect with
        :type pkey: :mod:`paramiko.PKey`
        :param num_retries: (Optional) Number of retries for connection attempts \
        before the client gives up. Defaults to 3.
        :type num_retries: int
        :param timeout: (Optional) Number of seconds to timeout connection \
        attempts before the client gives up. Defaults to 10.
        :type timeout: int
        :param forward_ssh_agent: (Optional) Turn on SSH agent forwarding - \
        equivalent to `ssh -A` from the `ssh` command line utility. \
        Defaults to True if not set.
        :type forward_ssh_agent: bool
        :param pool_size: (Optional) Greenlet pool size. Controls on how many\
        hosts to execute tasks in parallel. Defaults to 10. Values over 500 \
        are not likely to increase performance due to overhead in the single \
        thread running our event loop.
        :type pool_size: int
        :param proxy_host: (Optional) SSH host to tunnel connection through \
        so that SSH clients connect to self.host via client -> proxy_host -> \
        host
        :type proxy_host: str
        :param proxy_port: (Optional) SSH port to use to login to proxy host if \
        set. Defaults to 22.
        :type proxy_port: int
        :param agent: (Optional) SSH agent object to programmatically supply an \
        agent to override system SSH agent with
        :type agent: :mod:`pssh.agent.SSHAgent`
        :param host_config: (Optional) Per-host configuration for cases where \
        not all hosts use the same configuration values.
        :type host_config: dict
        :param channel_timeout: (Optional) Time in seconds before an SSH operation \
        times out.
        :type channel_timeout: int
        :type channel_timeout: int
        :param allow_agent: (Optional) set to False to disable connecting to \
        the SSH agent
        :type allow_agent: bool
        **Example Usage**
        
        >>> from pssh.pssh_client import ParallelSSHClient
        >>> from pssh.exceptions import AuthenticationException, \
                UnknownHostException, ConnectionErrorException
        
        >>> client = ParallelSSHClient(['myhost1', 'myhost2'])
        >>> try:
        >>> ... output = client.run_command('ls -ltrh /tmp/aasdfasdf', sudo=True)
        >>> except (AuthenticationException, UnknownHostException, ConnectionErrorException):
        >>> ... pass
        
        Commands have started executing at this point.
        Exit code(s) will not be available immediately.
        
        >>> print output

        ::
        
            {'myhost1': {'exit_code': None,
                         'stdout' : <generator>,
                         'stderr' : <generator>,
                         'cmd' : <greenlet>,
                         'exception' : None,
                         },
             'myhost2': {'exit_code': None,
                         'stdout' : <generator>,
                         'stderr' : <generator>,
                         'cmd' : <greenlet>,
                         'exception' : None,
            }}
        
        **Enabling host logger**
        
        There is a host logger in parallel-ssh that can be enabled to show stdout
        *in parallel* from remote commands on hosts as it comes in.
        
        This allows for stdout to be automatically displayed without having to
        print it serially per host.
        
        >>> import pssh.utils
        >>> pssh.utils.enable_host_logger()
        >>> output = client.run_command('ls -ltrh')
        [myhost1]     drwxrwxr-x 6 user group 4.0K Jan 1 HH:MM x
        [myhost2]     drwxrwxr-x 6 user group 4.0K Jan 1 HH:MM x
        
        Retrieve exit codes after commands have finished as below.
        
        ``exit_code`` in ``output`` will be ``None`` if command has not yet finished.
        
        `parallel-ssh` starts commands asynchronously to enable running multiple
        commands in parallel without blocking.
        
        Because of this, exit codes will not be immediately available even for
        commands that exit immediately.
        
        At least one of ::
        
        * Iterating over stdout/stderr
        * Calling `client.join(output)`
        * Calling `client.pool.join()` if no output is needed
        
        is necessary to cause `parallel-ssh` to wait for commands to finish and
        be able to gather exit codes.
        
        Either iterating over stdout/stderr or `client.join(output)` will cause exit
        codes to be available in output without explicitly calling `get_exit_codes`.
        
        Use ``client.join(output)`` to block until all commands have finished
        and gather exit codes at same time.
        
        `client.pool.join()` does not update output and will need a call to
        `get_exit_codes` as shown below.
        
        ``get_exit_codes`` is not a blocking function and will not wait for commands
        to finish.
        
        ``output`` parameter is modified in-place.
        
        >>> client.get_exit_codes(output)
        >>> for host in output:
        >>> ... print output[host]['exit_code']
        0
        0
        
        Print stdout serially per host as it becomes available.
        
        >>> for host in output: for line in output[host]['stdout']: print line
        [myhost1]     ls: cannot access /tmp/aasdfasdf: No such file or directory
        [myhost2]     ls: cannot access /tmp/aasdfasdf: No such file or directory
        
        **Example with specified private key**
        
        >>> import paramiko
        >>> client_key = paramiko.RSAKey.from_private_key_file('user.key')
        >>> client = ParallelSSHClient(['myhost1', 'myhost2'], pkey=client_key)
        
        **Multiple commands**
        
        >>> for cmd in ['uname', 'whoami']:
        ...    client.run_command(cmd)
        
        **Per-Host configuration**
        
        Per host configuration can be provided for any of user, password port
        and private key. Private key value is a :mod:`paramiko.PKey` object as
        returned by :mod:`pssh.utils.load_private_key`.
        
        :mod:`pssh.utils.load_private_key` accepts both file names and file-like
        objects and will attempt to load all available key types, returning
        `None` if they all fail.
        
        >>> from pssh.utils import load_private_key
        >>> host_config = { 'host1' : {'user': 'user1', 'password': 'pass',
        ...                            'port': 2222,
        ...                            'private_key': load_private_key('my_key.pem')},
        ...                 'host2' : {'user': 'user2', 'password': 'pass',
        ...                            'port': 2223,
        ...                            'private_key': load_private_key(open('my_other_key.pem'))},
        ...                 }
        >>> hosts = host_config.keys()
        >>> client = ParallelSSHClient(hosts, host_config=host_config)
        >>> client.run_command('uname')
        
        .. note ::
        
          **Connection persistence**
          
          Connections to hosts will remain established for the duration of the
          object's life. To close them, just `del` or reuse the object reference.
          
          >>> client = ParallelSSHClient(['localhost'])
          >>> output = client.run_command('ls -ltrh /tmp/aasdfasdf')
          >>> client.join(output)
          
          :netstat: ``tcp        0      0 127.0.0.1:53054         127.0.0.1:22            ESTABLISHED``
          
          Connection remains active after commands have finished executing. Any \
          additional commands will use the same connection.
          
          >>> del client
          
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
        self.proxy_host, self.proxy_port = proxy_host, proxy_port
        # To hold host clients
        self.host_clients = {}
        self.agent = agent
        self.allow_agent = allow_agent
        self.host_config = host_config if host_config else {}
        self.channel_timeout = channel_timeout

    def run_command(self, *args, **kwargs):
        """Run command on all hosts in parallel, honoring self.pool_size,
        and return output buffers.
        
        This function will block until all commands been *sent* to remote servers
        and then return immediately.
        
        Any connection and/or authentication exceptions will be raised here
        and need catching *unless* `run_command` is called with
        `stop_on_errors=False`.
        
        :param args: Positional arguments for command
        :type args: tuple
        :param sudo: (Optional) Run with sudo. Defaults to False
        :type sudo: bool
        :param user: (Optional) User to run command as. Requires sudo access \
        for that user from the logged in user account.
        :type user: str
        :param stop_on_errors: (Optional) Raise exception on errors running command. \
        Defaults to True. With stop_on_errors set to False, exceptions are instead \
        added to output of `run_command`. See example usage below.
        :type stop_on_errors: bool
        :param shell: (Optional) Override shell to use to run command with. \
        Defaults to logged in user's defined shell. Use the shell's command \
        syntax, eg `shell='bash -c'` or `shell='zsh -c'`.
        :type shell: str
        :param use_shell: (Optional) Run command with or without shell. Defaults \
        to True - use shell defined in user login to run command string
        :type use_shell: bool
        :rtype: Dictionary with host as key as per \
          :mod:`pssh.pssh_client.ParallelSSHClient.get_output`
        
        :raises: :mod:`pssh.exceptions.AuthenticationException` on authentication error
        :raises: :mod:`pssh.exceptions.UnknownHostException` on DNS resolution error
        :raises: :mod:`pssh.exceptions.ConnectionErrorException` on error connecting
        :raises: :mod:`pssh.exceptions.SSHException` on other undefined SSH errors
        
        **Example Usage**
        
        **Simple run command**
        
        >>> output = client.run_command('ls -ltrh')
        
        *print stdout for each command*
        
        >>> for host in output:
        >>>     for line in output[host]['stdout']: print line
        
        *Get exit codes after command has finished*
        
        >>> client.get_exit_codes(output)
        >>> for host in output:
        >>> ... print output[host]['exit_code']
        0
        0
        
        *Wait for completion, no stdout/stderr*
        
        >>> client.join(output)
        >>> print output[host]['exit_code']
        0
        
        *Run with sudo*
        
        >>> output = client.run_command('ls -ltrh', sudo=True)
        
        Capture stdout - **WARNING** - this will store the entirety of stdout
        into memory and may exhaust available memory if command output is
        large enough.
        
        Iterating over stdout/stderr by definition implies blocking until
        command has finished. To only see output as it comes in without blocking
        the host logger can be enabled - see `Enabling Host Logger` above.
        
        >>> for host in output:
        >>>     stdout = list(output[host]['stdout'])
        >>>     print "Complete stdout for host %s is %s" % (host, stdout,)
        
        **Expression as host list**
        
        Any type of iterator may be used as host list, including generator and
        list comprehension expressions.
        
        >>> hosts = ['dc1.myhost1', 'dc2.myhost2']
        # List comprehension
        >>> client = ParallelSSHClient([h for h in hosts if h.find('dc1')])
        # Generator
        >>> client = ParallelSSHClient((h for h in hosts if h.find('dc1')))
        # Filter
        >>> client = ParallelSSHClient(filter(lambda h: h.find('dc1'), hosts))
        >>> client.run_command(<..>)
        
        .. note ::
        
          Since iterators by design only iterate over a sequence once then stop,
          `client.hosts` should be re-assigned after each call to `run_command`
          when using iterators as target of `client.hosts`.
        
        **Overriding host list**
        
        Host list can be modified in place. Call to `run_command` will create
        new connections as necessary and output will only contain output for
        hosts command ran on.
        
        >>> client.hosts = ['otherhost']
        >>> print client.run_command('exit 0')
        >>> {'otherhost': {'exit_code': None}, <..>}
        
        **Run multiple commands in parallel**
        
        This short example demonstrates running long running commands in
        parallel, how long it takes for all commands to start, blocking until
        they complete and how long it takes for all commands to complete.
        
        See examples directory for complete script. ::
        
          output = []
          host = 'localhost'
          
          # Run 10 five second sleeps
          cmds = ['sleep 5' for _ in xrange(10)]
          start = datetime.datetime.now()
          for cmd in cmds:
              output.append(client.run_command(cmd, stop_on_errors=False))
          end = datetime.datetime.now()
          print "Started %s commands in %s" % (len(cmds), end-start,)
          start = datetime.datetime.now()
          for _output in output:
              for line in _output[host]['stdout']:
                  print line
          end = datetime.datetime.now()
          print "All commands finished in %s" % (end-start,)
        
        *Output*
        
        ::
        
          Started 10 commands in 0:00:00.428629
          All commands finished in 0:00:05.014757
        
        **Output dictionary**
        
        ::
        
          {'myhost1': {'exit_code': exit code if ready else None,
                       'channel' : SSH channel of command,
                       'stdout'  : <iterable>,
                       'stderr'  : <iterable>,
                       'cmd'     : <greenlet>},
                       'exception' : None}
        
        **Do not stop on errors, return per-host exceptions in output**
        
        >>> output = client.run_command('ls -ltrh', stop_on_errors=False)
        >>> client.join(output)
        >>> print output
        
        ::
        
          {'myhost1': {'exit_code': None,
                       'channel' : None,
                       'stdout'  : None,
                       'stderr'  : None,
                       'cmd'     : None,
                       'exception' : ConnectionErrorException(
                           "Error connecting to host '%s:%s' - %s - retry %s/%s",
                           host, port, 'Connection refused', 3, 3)}}
        
        """
        stop_on_errors = kwargs.pop('stop_on_errors', True)
        cmds = [self.pool.spawn(self._exec_command, host, *args, **kwargs)
                for host in self.hosts]
        output = {}
        for cmd in cmds:
            try:
                self.get_output(cmd, output)
            except Exception, ex:
                if stop_on_errors:
                    raise ex
        return output
    
    def exec_command(self, *args, **kwargs):
        """Run command on all hosts in parallel, honoring `self.pool_size`
        
        **Deprecated by** :mod:`pssh.pssh_client.ParallelSSHClient.run_command`
        
        :param args: Position arguments for command
        :type args: tuple
        :param kwargs: Keyword arguments for command
        :type kwargs: dict
        
        :rtype: List of :mod:`gevent.Greenlet`"""
        warnings.warn("This method is being deprecated and will be removed in \
future releases - use self.run_command instead", DeprecationWarning)
        return [self.pool.spawn(self._exec_command, host, *args, **kwargs)
                for host in self.hosts]
    
    def _get_host_config_values(self, host):
        _user = self.host_config.get(host, {}).get('user', self.user)
        _port = self.host_config.get(host, {}).get('port', self.port)
        _password = self.host_config.get(host, {}).get('password', self.password)
        _pkey = self.host_config.get(host, {}).get('private_key', self.pkey)
        return _user, _port, _password, _pkey
    
    def _exec_command(self, host, *args, **kwargs):
        """Make SSHClient, run command on host"""
        if not host in self.host_clients or not self.host_clients[host]:
            _user, _port, _password, _pkey = self._get_host_config_values(host)
            self.host_clients[host] = SSHClient(host, user=_user,
                                                password=_password,
                                                port=_port, pkey=_pkey,
                                                forward_ssh_agent=self.forward_ssh_agent,
                                                num_retries=self.num_retries,
                                                timeout=self.timeout,
                                                proxy_host=self.proxy_host,
                                                proxy_port=self.proxy_port,
                                                allow_agent=self.allow_agent, agent=self.agent,
                                                channel_timeout=self.channel_timeout)
        return self.host_clients[host].exec_command(*args, **kwargs)
    
    def get_output(self, cmd, output):
        """Get output from command.
        
        :param cmd: Command to get output from
        :type cmd: :mod:`gevent.Greenlet`
        :param output: Dictionary containing output to be updated with output \
        from cmd
        :type output: dict
        :rtype: None
        
        `output` parameter is modified in-place and has the following structure
        
        ::
        
          {'myhost1': {'exit_code': exit code if ready else None,
                       'channel' : SSH channel of command,
                       'stdout'  : <iterable>,
                       'stderr'  : <iterable>,
                       'cmd'     : <greenlet>,
                       'exception' : <exception object if applicable>}}
        
        Stdout and stderr are also logged via the logger named ``host_logger``
        which can be enabled by calling ``enable_host_logger``
        
        **Example usage**:
        
        >>> output = client.get_output()
        >>> for host in output: for line in output[host]['stdout']: print line
        <stdout>
        >>> # Get exit code after command has finished
        >>> self.get_exit_code(output[host])
        0
        """
        try:
            (channel, host, stdout, stderr) = cmd.get()
        except Exception, ex:
            try:
                host = ex.args[1]
            except IndexError:
                logger.error("Got exception with no host argument - "
                             "cannot update output data with %s", ex)
                raise ex
            self._update_host_output(output, host, None, None, None, None, cmd,
                                     exception=ex)
            raise ex
        self._update_host_output(output, host, self._get_exit_code(channel),
                                 channel, stdout, stderr, cmd)

    def _update_host_output(self, output, host, exit_code, channel, stdout,
                            stderr, cmd, exception=None):
        """Update host output with given data"""
        if host in output:
            new_host = "_".join([host,
                                 ''.join(random.choice(
                                     string.ascii_lowercase + string.digits)
                                     for _ in xrange(8))])
            logger.warning("Already have output for host %s - changing host "
                           "key for %s to %s", host, host, new_host)
            host = new_host
        output.setdefault(host, {})
        output[host].update({'exit_code' : exit_code,
                             'channel' : channel,
                             'stdout' : self._read_buff_ex_code(stdout, output),
                             'stderr' : self._read_buff_ex_code(stderr, output),
                             'cmd' : cmd,
                             'exception' : exception,})

    def _read_buff_ex_code(self, _buffer, output):
        if _buffer:
            for line in _buffer:
                yield line
        self.get_exit_codes(output)

    def join(self, output):
        """Block until all remote commands in output have finished
        and retrieve exit codes"""
        for host in output:
            stdout = output[host].get('stdout')
            if stdout:
                for _ in stdout:
                    pass
        self.get_exit_codes(output)
    
    def get_exit_codes(self, output):
        """Get exit code for all hosts in output *if available*.
        Output parameter is modified in-place.
        
        :param output: As returned by :mod:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: None
        """
        for host in output:
            output[host].update({'exit_code': self.get_exit_code(output[host])})

    def get_exit_code(self, host_output):
        """Get exit code from host output *if available*.
        
        :param host_output: Per host output as returned by \
          :mod:`pssh.pssh_client.ParallelSSHClient.get_output`
        :rtype: int or None if exit code not ready"""
        if not 'channel' in host_output:
            logger.error("%s does not look like host output..", host_output,)
            return
        channel = host_output['channel']
        return self._get_exit_code(channel)

    def _get_exit_code(self, channel):
        """Get exit code from channel if ready"""
        if not channel or not channel.exit_status_ready():
            return
        channel.close()
        return channel.recv_exit_status()

    def get_stdout(self, greenlet, return_buffers=False):
        """Get/print stdout from greenlet and return exit code for host
        
        **Deprecated** - use :mod:`pssh.pssh_client.ParallelSSHClient.get_output` instead.
        
        :param greenlet: Greenlet object containing an \
        SSH channel reference, hostname, stdout and stderr buffers
        :type greenlet: :mod:`gevent.Greenlet`
        :param return_buffers: Flag to turn on returning stdout and stderr \
        buffers along with exit code. Defaults to off.
        :type return_buffers: bool
        :rtype: Dictionary containing ``{host: {'exit_code': exit code}}`` entry \
        for example ``{'myhost1': {'exit_code': 0}}``
        :rtype: With ``return_buffers=True``: ``{'myhost1': {'exit_code': 0,
                                                             'channel' : None or SSH channel of command if command is still executing,
                                                             'stdout' : <iterable>,
                                                             'stderr' : <iterable>,}}``
        """
        warnings.warn("This method is being deprecated and will be removed in"
                      "future releases - use self.get_output instead", DeprecationWarning)
        gevent.sleep(.2)
        channel, host, stdout, stderr = greenlet.get()
        if channel.exit_status_ready():
            channel.close()
        else:
            logger.debug("Command still executing on get_stdout call - not closing channel and returning None as exit code.")
            # If channel is not closed we cannot get full stdout/stderr so must return buffers
            return_buffers = True
        # Channel must be closed or reading stdout/stderr will block forever
        if not return_buffers and channel.closed:
            for _ in stdout:
                pass
            for _ in stderr:
                pass
            return {host: {'exit_code': channel.recv_exit_status(),}}
        gevent.sleep(.2)
        return {host: {'exit_code': channel.recv_exit_status() if channel.exit_status_ready() else None,
                       'channel' : channel if not channel.closed else None,
                       'stdout' : stdout,
                       'stderr' : stderr, }}

    def copy_file(self, local_file, remote_file, recurse=False):
        """Copy local file to remote file in parallel
        
        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool
        
        :raises: :mod:`ValueError` when a directory is supplied to local_file \
        and recurse is not set
        
        .. note ::
          Remote directories in `remote_file` that do not exist will be
          created as long as permissions allow.
        
        :rtype: List(:mod:`gevent.Greenlet`) of greenlets for remote copy \
        commands
        """
        return [self.pool.spawn(self._copy_file, host, local_file, remote_file,
                                {'recurse' : recurse})
                for host in self.hosts]

    def _copy_file(self, host, local_file, remote_file, recurse=False):
        """Make sftp client, copy file"""
        if not host in self.host_clients or not self.host_clients[host]:
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
        return self.host_clients[host].copy_file(local_file, remote_file,
                                                 recurse=recurse)
