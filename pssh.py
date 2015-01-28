#!/usr/bin/env python

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

"""Asynchronous parallel SSH library

parallel-ssh uses asychronous network requests - there is *no* multi-threading or multi-processing used.

This is a *requirement* for commands on many (hundreds/thousands/hundreds of thousands) of hosts which would grind a system to a halt simply by having so many processes/threads all wanting to execute if done with multi-threading/processing.

The `libev event loop library <http://software.schmorp.de/pkg/libev.html>`_ is utilised on nix systems. Windows is not supported.

See :mod:`pssh.ParallelSSHClient` and :mod:`pssh.SSHClient` for class documentation.
"""

from gevent import monkey
monkey.patch_all()
import gevent.pool
import warnings
from socket import gaierror as sock_gaierror, error as sock_error
import logging
import paramiko
import os

host_logger = logging.getLogger('pssh.host_logger')
handler = logging.StreamHandler()
host_log_format = logging.Formatter('%(message)s')
handler.setFormatter(host_log_format)
host_logger.addHandler(handler)
host_logger.setLevel(logging.INFO)
DEFAULT_RETRIES = 3

logger = logging.getLogger(__name__)

class UnknownHostException(Exception):
    """Raised when a host is unknown (dns failure)"""
    pass


class ConnectionErrorException(Exception):
    """Raised on error connecting (connection refused/timed out)"""
    pass


class AuthenticationException(Exception):
    """Raised on authentication error (user/password/ssh key error)"""
    pass


class SSHException(Exception):
    """Raised on SSHException error - error authenticating with SSH server"""
    pass


class SSHClient(object):
    """Wrapper class over paramiko.SSHClient with sane defaults
    Honours ~/.ssh/config and /etc/ssh/ssh_config entries for host username \
    overrides"""

    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None, forward_ssh_agent=True,
                 num_retries=DEFAULT_RETRIES, _agent=None, timeout=None,
                 proxy_host=None, proxy_port=22):
        """Connect to host honouring any user set configuration in ~/.ssh/config \
        or /etc/ssh/ssh_config
        
        :param host: Hostname to connect to
        :type host: str
        :param user: (Optional) User to login as. Defaults to logged in user or \
        user from ~/.ssh/config if set
        :type user: str
        :param password: (Optional) Password to use for login. Defaults to\
        no password
        :type password: str
        :param port: (Optional) Port number to use for SSH connection. Defaults\
        to None which uses SSH default
        :type port: int
        :param pkey: (Optional) Client's private key to be used to connect with
        :type pkey: :mod:`paramiko.PKey`
        :param num_retries: (Optional) Number of retries for connection attempts\
        before the client gives up. Defaults to 3.
        :type num_retries: int
        :param timeout: (Optional) Number of seconds to timout connection attempts\
        before the client gives up. Defaults to 10.
        :type timeout: int
        :param forward_ssh_agent: (Optional) Turn on SSH agent forwarding - \
        equivalent to `ssh -A` from the `ssh` command line utility. \
        Defaults to True if not set.
        :type forward_ssh_agent: bool
        :param _agent: (Optional) Override SSH agent object with the provided. \
        This allows for overriding of the default paramiko behaviour of \
        connecting to local SSH agent to lookup keys with our own SSH agent. \
        Only really useful for testing, hence the internal variable prefix.
        :type _agent: :mod:`paramiko.agent.Agent`
        :param proxy_host: (Optional) SSH host to tunnel connection through \
        so that SSH clients connects to self.host via client -> proxy_host -> host
        :type proxy_host: str
        :param proxy_port: (Optional) SSH port to use to login to proxy host if \
        set. Defaults to 22.
        :type proxy_port: int
        """
        ssh_config = paramiko.SSHConfig()
        _ssh_config_file = os.path.sep.join([os.path.expanduser('~'),
                                             '.ssh',
                                             'config'])
        # Load ~/.ssh/config if it exists to pick up username
        # and host address if set
        if os.path.isfile(_ssh_config_file):
            ssh_config.parse(open(_ssh_config_file))
        host_config = ssh_config.lookup(host)
        resolved_address = (host_config['hostname'] if
                            'hostname' in host_config
                            else host)
        _user = host_config['user'] if 'user' in host_config else None
        user = user if user else _user
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        self.forward_ssh_agent = forward_ssh_agent
        self.client = client
        self.user = user
        self.password = password
        self.pkey = pkey
        self.port = port if port else 22
        self.host = resolved_address
        if _agent:
            self.client._agent = _agent
        self.num_retries = num_retries
        self.timeout = timeout
        self.proxy_host, self.proxy_port = proxy_host, proxy_port
        self.proxy_client = None
        if self.proxy_host and self.proxy_port:
            logger.debug("Proxy configured for destination host %s - Proxy host: %s:%s",
                         self.host, self.proxy_host, self.proxy_port,)
            self._connect_tunnel()
        else:
            self._connect(self.client, self.host, self.port)

    def _connect_tunnel(self):
        """Connects to SSH server via an intermediate SSH tunnel server.
        client (me) -> tunnel (ssh server to proxy through) -> \
        destination (ssh server to run command)
        :rtype: `:mod:paramiko.SSHClient` Client to remote SSH destination
        via intermediate SSH tunnel server."""
        self.proxy_client = paramiko.SSHClient()
        self.proxy_client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        self._connect(self.proxy_client, self.proxy_host, self.proxy_port)
        logger.info("Connecting via SSH proxy %s:%s -> %s:%s", self.proxy_host,
                    self.proxy_port, self.host, self.port,)
        proxy_channel = self.proxy_client.get_transport().\
          open_channel('direct-tcpip', (self.host, self.port,),
                       ('127.0.0.1', 0))
        return self._connect(self.client, self.host, self.port, sock=proxy_channel)
        
    def _connect(self, client, host, port, sock=None, retries=1):
        """Connect to host
        
        :raises: :mod:`pssh.AuthenticationException` on authentication error
        :raises: :mod:`pssh.UnknownHostException` on DNS resolution error
        :raises: :mod:`pssh.ConnectionErrorException` on error connecting
        :raises: :mod:`pssh.SSHException` on other undefined SSH errors
        """
        try:
            client.connect(host, username=self.user,
                           password=self.password, port=port,
                           pkey=self.pkey,
                           sock=sock, timeout=self.timeout)
        except sock_gaierror, ex:
            logger.error("Could not resolve host '%s' - retry %s/%s",
                         self.host, retries, self.num_retries)
            while retries < self.num_retries:
                gevent.sleep(5)
                return self._connect(client, host, port, sock=sock,
                                     retries=retries+1)
            raise UnknownHostException("%s - %s - retry %s/%s",
                                       str(ex.args[1]),
                                       self.host, retries, self.num_retries)
        except sock_error, ex:
            logger.error("Error connecting to host '%s:%s' - retry %s/%s",
                         self.host, self.port, retries, self.num_retries)
            while retries < self.num_retries:
                gevent.sleep(5)
                return self._connect(client, host, port, sock=sock,
                                     retries=retries+1)
            error_type = ex.args[1] if len(ex.args) > 1 else ex.args[0]
            raise ConnectionErrorException("%s for host '%s:%s' - retry %s/%s",
                                           str(error_type), self.host, self.port,
                                           retries, self.num_retries,)
        except paramiko.AuthenticationException, ex:
            raise AuthenticationException(ex)
        # SSHException is more general so should be below other types
        # of SSH failure
        except paramiko.SSHException, ex:
            logger.error("General SSH error - %s", ex)
            raise SSHException(ex)

    def exec_command(self, command, sudo=False, user=None, **kwargs):
        """Wrapper to :mod:`paramiko.SSHClient.exec_command`

        Opens a new SSH session with a new pty and runs command with given \
        `kwargs` if any. Greenlet then yields (sleeps) while waiting for \
        command to finish executing or channel to close indicating the same.

        :param command: Shell command to execute
        :type command: str
        :param sudo: (Optional) Run with sudo. Defaults to False
        :type sudo: bool
        :param kwargs: (Optional) Keyword arguments to be passed to remote \
        command
        :type kwargs: dict
        :rtype: Tuple of `(channel, hostname, stdout, stderr)`. \
        Channel is the remote SSH channel, needed to ensure all of stdout has \
        been got, hostname is remote hostname the copy is to, stdout and \
        stderr are buffers containing command output.
        """
        channel = self.client.get_transport().open_session()
        if self.forward_ssh_agent:
            agent_handler = paramiko.agent.AgentRequestHandler(channel)
        channel.get_pty()
        if self.timeout:
            channel.settimeout(self.timeout)
        _stdout, _stderr = channel.makefile('rb'), \
                           channel.makefile_stderr('rb')
        stdout, stderr = self._read_output_buffer(_stdout,), \
                         self._read_output_buffer(_stderr,
                                                  prefix='\t[err]')
        if sudo and not user:
            command = 'sudo -S bash -c "%s"' % command.replace('"', '\\"')
        elif user:
            command = 'sudo -u %s -S bash -c "%s"' % (
                user, command.replace('"', '\\"'),)
        else:
            command = 'bash -c "%s"' % command.replace('"', '\\"')
        logger.debug("Running command %s on %s", command, self.host)
        channel.exec_command(command, **kwargs)
        logger.debug("Command started")
        while not (channel.recv_ready() or channel.closed):
            gevent.sleep(.2)
        return channel, self.host, stdout, stderr

    def _read_output_buffer(self, output_buffer, prefix=''):
        """Read from output buffers and log to host_logger"""
        for line in output_buffer:
            output = line.strip()
            host_logger.info("[%s]%s\t%s", self.host, prefix, output,)
            yield output

    def _make_sftp(self):
        """Make SFTP client from open transport"""
        transport = self.client.get_transport()
        transport.open_session()
        return paramiko.SFTPClient.from_transport(transport)

    def mkdir(self, sftp, directory):
        """Make directory via SFTP channel
        
        :param sftp: SFTP client object
        :type sftp: :mod:`paramiko.SFTPClient`
        :param directory: Remote directory to create
        :type directory: str

        Catches and logs at error level remote IOErrors on creating directory."""
        try:
            sftp.mkdir(directory)
        except IOError, error:
            logger.error("Error occured creating directory on %s - %s",
                         self.host, error)

    def copy_file(self, local_file, remote_file):
        """Copy local file to host via SFTP/SCP

        Copy is done natively using SFTP/SCP version 2 protocol, no scp command \
        is used or required.

        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        """
        sftp = self._make_sftp()
        destination = remote_file.split(os.path.sep)
        remote_file = os.path.sep.join(destination)
        destination = destination[:-1]
        for directory in destination:
            try:
                sftp.stat(directory)
            except IOError:
                self.mkdir(sftp, directory)
        try:
            sftp.put(local_file, remote_file)
        except Exception, error:
            logger.error("Error occured copying file to host %s - %s",
                         self.host, error)
        else:
            logger.info("Copied local file %s to remote destination %s:%s",
                        local_file, self.host, remote_file)

class ParallelSSHClient(object):
    """Uses :mod:`pssh.SSHClient`, performs tasks over SSH on multiple hosts in \
    parallel.

    Connections to hosts are established in parallel when ``run_command`` is called,
    therefor any connection and/or authentication exceptions will happen on the
    call to ``run_command`` and need to be caught."""

    def __init__(self, hosts,
                 user=None, password=None, port=None, pkey=None,
                 forward_ssh_agent=True, num_retries=DEFAULT_RETRIES, timeout=None,
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
        :param timeout: (Optional) Number of seconds to timout connection \
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
        :param kwargs: Keyword arguments for command
        :type kwargs: dict

        :rtype: Dictionary with host as key as per :mod:`ParallelSSH.get_output`
        
        :raises: :mod:`pssh.AuthenticationException` on authentication error
        :raises: :mod:`pssh.UnknownHostException` on DNS resolution error
        :raises: :mod:`pssh.ConnectionErrorException` on error connecting
        :raises: :mod:`pssh.SSHException` on other undefined SSH errors

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
        for host in self.hosts:
            self.pool.spawn(self._exec_command, host, *args, **kwargs)
        return self.get_output()
    
    def exec_command(self, *args, **kwargs):
        """Run command on all hosts in parallel, honoring `self.pool_size`
        
        **Deprecated by** :mod:`pssh.ParallelSSHClient.run_command`
        
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

    def get_output(self, commands=None):
        """Get output from running commands.
        
        :param commands: (Optional) Override commands to get output from.\
        Uses running commands in pool if not given.
        :type commands: :mod:`gevent.Greenlet`
        :rtype: Dictionary with host as key as in:

        ::
        
          {'myhost1': {'exit_code': exit code if ready else None,
                       'channel' : SSH channel of command,
                       'stdout'  : <iterable>,
                       'stderr'  : <iterable>,
                       'cmd'     : <greenlet>}}
        
        Stdout and stderr are also logged via the logger named ``host_logger``
        which is enabled by default.
        ``host_logger`` output can be disabled by removing its handler.
        
        >>> logger = logging.getLogger('pssh.host_logger')
        >>> for handler in logger.handlers: logger.removeHandler(handler)
        
        **Example usage**:
        
        >>> output = client.get_output()
        >>> for host in output: print output[host]['stdout']
        <stdout>
        >>> # Get exit code after command has finished
        >>> self.get_exit_code(output[host])
        0
        """
        if not commands:
            commands = list(self.pool.greenlets)
        output = {}
        for cmd in commands:
            (channel, host, stdout, stderr) = cmd.get()
            output.setdefault(host, {})
            output[host].update({'exit_code': self._get_exit_code(channel),
                                 'channel' : channel,
                                 'stdout' : stdout,
                                 'stderr' : stderr,
                                 'cmd' : cmd, })
        return output

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
        warnings.warn("This method is being deprecated and will be removed in \
future releases - use self.get_output instead", DeprecationWarning)
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
