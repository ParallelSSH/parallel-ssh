# This file is part of parallel-ssh.

# Copyright (C) 2015 Panos Kittenis

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


from gevent import monkey
monkey.patch_all()
import logging
import gevent.pool
import gevent.hub
gevent.hub.Hub.NOT_ERROR = (Exception,)
import warnings
from .constants import DEFAULT_RETRIES
from .ssh_client import SSHClient


host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger('pssh')


class ParallelSSHClient(object):
    """Uses :mod:`pssh.ssh_client.SSHClient`, performs tasks over SSH on multiple hosts in \
    parallel.

    Connections to hosts are established in parallel when ``run_command`` is called,
    therefor any connection and/or authentication exceptions will happen on the
    call to ``run_command`` and need to be caught."""

    def __init__(self, hosts,
                 user=None, password=None, port=None, pkey=None,
                 forward_ssh_agent=True, num_retries=DEFAULT_RETRIES, timeout=120,
                 pool_size=10, proxy_host=None, proxy_port=22):
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
        hosts to execute tasks in parallel. Defaults to number of hosts or 10, \
        whichever is lower. Pool size will be *equal to* number of hosts if number\
        of hosts is lower than the pool size specified as that would only \
        increase overhead with no benefits.
        :type pool_size: int
        :param proxy_host: (Optional) SSH host to tunnel connection through \
        so that SSH clients connect to self.host via client -> proxy_host -> \
        host
        :type proxy_host: str
        :param proxy_port: (Optional) SSH port to use to login to proxy host if \
        set. Defaults to 22.
        :type proxy_port: int
        
        **Example**

        >>> from pssh import ParallelSSHClient, AuthenticationException, \
UnknownHostException, ConnectionErrorException
        >>> client = ParallelSSHClient(['myhost1', 'myhost2'])
        >>> try:
        >>> ... output = client.run_command('ls -ltrh /tmp/aasdfasdf', sudo=True)
        >>> except (AuthenticationException, UnknownHostException, ConnectionErrorException):
        >>> ... return
        >>> # Commands have started executing at this point
        >>> # Exit code will probably not be available immediately
        >>> print output
        >>> {'myhost1': {'exit_code': None,
                         'stdout' : <generator>,
                         'stderr' : <generator>,
                         'cmd' : <greenlet>,
                         },
             'myhost2': {'exit_code': None,
                         'stdout' : <generator>,
                         'stderr' : <generator>,
                         'cmd' : <greenlet>,
            }}
        >>> # Print output as it comes in. 
        >>> for host in output: for line in output[host]['stdout']: print line
        [myhost1]     ls: cannot access /tmp/aasdfasdf: No such file or directory
        [myhost2]     ls: cannot access /tmp/aasdfasdf: No such file or directory
        >>> # Retrieve exit code after commands have finished
        >>> # `get_exit_code` will return `None` if command has not finished
        >>> print client.get_exit_code(output[host])
        0

        **Example with specified private key**

        >>> import paramiko
        >>> client_key = paramiko.RSAKey.from_private_key_file('user.key')
        >>> client = ParallelSSHClient(['myhost1', 'myhost2'], pkey=client_key)
        
        .. note ::
        
          **Connection persistence**
          
          Connections to hosts will remain established for the duration of the
          object's life. To close them, just `del` or reuse the object reference.
          
          >>> client = ParallelSSHClient(['localhost'])
          >>> output = client.run_command('ls -ltrh /tmp/aasdfasdf')
          >>> client.pool.join()
          
          :netstat: ``tcp        0      0 127.0.0.1:53054         127.0.0.1:22            ESTABLISHED``
          
          Connection remains active after commands have finished executing. Any \
          additional commands will use the same connection.
          
          >>> del client
          
          Connection is terminated.
        """
        self.pool_size = len(hosts) if len(hosts) < pool_size else pool_size
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
        self.host_clients = dict((host, None) for host in hosts)

    def run_command(self, *args, **kwargs):
        """Run command on all hosts in parallel, honoring self.pool_size,
        and return output buffers.

        This function will block until all commands have **started** and
        then return immediately. Any connection and/or authentication exceptions
        will be raised here and need catching.

        :param args: Positional arguments for command
        :type args: tuple
        :param sudo: (Optional) Run with sudo. Defaults to False
        :type sudo: bool
        :param kwargs: Keyword arguments for command
        :type kwargs: dict
        :param stop_on_errors: (Optional) Raise exception on errors running command. \
        Defaults to True.
        :type stop_on_errors: bool
        :rtype: Dictionary with host as key as per :mod:`pssh.pssh_client.ParallelSSH.get_output`
        
        :raises: :mod:`pssh.exceptions.AuthenticationException` on authentication error
        :raises: :mod:`pssh.exceptions.UnknownHostException` on DNS resolution error
        :raises: :mod:`pssh.exceptions.ConnectionErrorException` on error connecting
        :raises: :mod:`pssh.exceptions.SSHException` on other undefined SSH errors

        **Example Usage**
        
        >>> output = client.run_command('ls -ltrh')

        print stdout for each command:
        
        >>> for host in output:
        >>>     for line in output[host]['stdout']: print line

        Get exit code after command has finished:

        >>> for host in output:
        >>>     for line in output[host]['stdout']: print line
        >>>     exit_code = client.get_exit_code(output[host])
        
        Wait for completion, no stdout:
        
        >>> client.pool.join()

        Run with sudo:

        >>> output = client.run_command('ls -ltrh', sudo=True)
        
        Capture stdout - **WARNING** - this will store the entirety of stdout
        into memory and may exhaust available memory if command output is
        large enough:
        
        >>> for host in output:
        >>>     stdout = list(output[host]['stdout'])
        >>>     print "Complete stdout for host %s is %s" % (host, stdout,)

        **Example Output**

        ::
        
          {'myhost1': {'exit_code': exit code if ready else None,
                       'channel' : SSH channel of command,
                       'stdout'  : <iterable>,
                       'stderr'  : <iterable>,
                       'cmd'     : <greenlet>}}

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

    def _exec_command(self, host, *args, **kwargs):
        """Make SSHClient, run command on host"""
        if not self.host_clients[host]:
            self.host_clients[host] = SSHClient(host, user=self.user,
                                                password=self.password,
                                                port=self.port, pkey=self.pkey,
                                                forward_ssh_agent=self.forward_ssh_agent,
                                                num_retries=self.num_retries,
                                                timeout=self.timeout,
                                                proxy_host=self.proxy_host,
                                                proxy_port=self.proxy_port)
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
                logger.error("Got exception with no host argument - cannot update output data with %s", ex)
                raise ex
            output.setdefault(host, {})
            output[host].update({'exit_code' : None,
                                 'channel' : None,
                                 'stdout' : None,
                                 'stderr' : None,
                                 'cmd' : cmd,
                                 'exception' : ex,})
            raise ex
        output.setdefault(host, {})
        output[host].update({'exit_code': self._get_exit_code(channel),
                             'channel' : channel,
                             'stdout' : stdout,
                             'stderr' : stderr,
                             'cmd' : cmd, })

    def get_exit_codes(self, output):
        """Get exit code for all hosts in output if available.
        Output parameter is modified in-place.
        
        :param output: As returned by `self.get_output`
        :rtype: None
        """
        for host in output:
            output[host].update({'exit_code': self.get_exit_code(output[host])})

    def get_exit_code(self, host_output):
        """Get exit code from host output if available
        :param host_output: Per host output as returned by `self.get_output`
        :rtype: int or None if exit code not ready"""
        if not 'channel' in host_output:
            logger.error("%s does not look like host output..", host_output,)
            return
        channel = host_output['channel']
        return self._get_exit_code(channel)

    def _get_exit_code(self, channel):
        """Get exit code from channel if ready"""
        if not channel.exit_status_ready():
            return
        channel.close()
        return channel.recv_exit_status()

    def get_stdout(self, greenlet, return_buffers=False):
        """Get/print stdout from greenlet and return exit code for host
        
        **Deprecated** - use self.get_output() instead.
        
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

    def copy_file(self, local_file, remote_file):
        """Copy local file to remote file in parallel
        
        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str

        .. note ::
          Remote directories in `remote_file` that do not exist will be
          created as long as permissions allow.

        .. note ::
          Path separation is handled client side so it is possible to copy
          to/from hosts with differing path separators, like from/to Linux
          and Windows.

        :rtype: List(:mod:`gevent.Greenlet`) of greenlets for remote copy \
        commands
        """
        return [self.pool.spawn(self._copy_file, host, local_file, remote_file)
                for host in self.hosts]

    def _copy_file(self, host, local_file, remote_file):
        """Make sftp client, copy file"""
        if not self.host_clients[host]:
            self.host_clients[host] = SSHClient(host, user=self.user,
                                                password=self.password,
                                                port=self.port, pkey=self.pkey,
                                                forward_ssh_agent=self.forward_ssh_agent)
        return self.host_clients[host].copy_file(local_file, remote_file)
