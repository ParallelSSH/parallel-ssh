# This file is part of parallel-ssh.

# Copyright (C) 2015- Panos Kittenis

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


"""Package containing SSHClient class."""

import sys
from gevent import sleep
import paramiko
from paramiko.ssh_exception import ChannelException
import os
from socket import gaierror as sock_gaierror, error as sock_error
from .exceptions import UnknownHostException, AuthenticationException, \
     ConnectionErrorException, SSHException
from .constants import DEFAULT_RETRIES
from .utils import read_openssh_config
import logging

host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger(__name__)


class SSHClient(object):
    """Wrapper class over paramiko.SSHClient with sane defaults
    Honours ~/.ssh/config and /etc/ssh/ssh_config entries for host username \
    overrides"""
    
    def __init__(self, host,
                 user=None, password=None, port=None,
                 pkey=None, forward_ssh_agent=True,
                 num_retries=DEFAULT_RETRIES, agent=None,
                 allow_agent=True, timeout=10, proxy_host=None,
                 proxy_port=22, proxy_user=None, proxy_password=None,
                 proxy_pkey=None, channel_timeout=None,
                 _openssh_config_file=None):
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
        :param timeout: (Optional) Number of seconds to timeout connection attempts\
        before the client gives up. Defaults to 10.
        :type timeout: int
        :param forward_ssh_agent: (Optional) Turn on SSH agent forwarding - \
        equivalent to `ssh -A` from the `ssh` command line utility. \
        Defaults to True if not set.
        :type forward_ssh_agent: bool
        :param agent: (Optional) Override SSH agent object with the provided. \
        This allows for overriding of the default paramiko behaviour of \
        connecting to local SSH agent to lookup keys with our own SSH agent \
        object.
        :type agent: :mod:`paramiko.agent.Agent`
        :param forward_ssh_agent: (Optional) Turn on SSH agent forwarding - \
        equivalent to `ssh -A` from the `ssh` command line utility. \
        Defaults to True if not set.
        :type forward_ssh_agent: bool
        :param proxy_host: (Optional) SSH host to tunnel connection through \
        so that SSH clients connects to self.host via client -> proxy_host -> host
        :type proxy_host: str
        :param proxy_port: (Optional) SSH port to use to login to proxy host if \
        set. Defaults to 22.
        :type proxy_port: int
        :param channel_timeout: (Optional) Time in seconds before an SSH operation \
        times out.
        :type channel_timeout: int
        :param allow_agent: (Optional) set to False to disable connecting to \
        the SSH agent
        :type allow_agent: bool
        """
        try:
            host, _user, _port, _pkey = read_openssh_config(
                host, config_file=_openssh_config_file)
        except TypeError:
            host, _user, _port, _pkey = host, None, 22, None
        user = user if user else _user
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        self.forward_ssh_agent = forward_ssh_agent
        self.client = client
        self.user = user
        self.password = password
        self.pkey = pkey if pkey else _pkey
        self.port = port if port else _port
        self.host = host
        self.allow_agent = allow_agent
        if agent:
            self.client._agent = agent
        self.num_retries = num_retries
        self.timeout = timeout
        self.channel_timeout = channel_timeout
        self.proxy_host, self.proxy_port, self.proxy_user, self.proxy_password, \
          self.proxy_pkey = proxy_host, proxy_port, proxy_user, \
          proxy_password, proxy_pkey
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
        via intermediate SSH tunnel server.
        """
        self.proxy_client = paramiko.SSHClient()
        self.proxy_client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        self._connect(self.proxy_client, self.proxy_host, self.proxy_port,
                      user=self.proxy_user, password=self.proxy_password,
                      pkey=self.proxy_pkey)
        logger.info("Connecting via SSH proxy %s:%s -> %s:%s", self.proxy_host,
                    self.proxy_port, self.host, self.port,)
        try:
          proxy_channel = self.proxy_client.get_transport().open_channel(
            'direct-tcpip', (self.host, self.port,), ('127.0.0.1', 0))
          sleep(0)
          return self._connect(self.client, self.host, self.port, sock=proxy_channel)
        except ChannelException, ex:
          error_type = ex.args[1] if len(ex.args) > 1 else ex.args[0]
          raise ConnectionErrorException("Error connecting to host '%s:%s' - %s",
                                         self.host, self.port,
                                         str(error_type))
    
    def _connect(self, client, host, port, sock=None, retries=1,
                 user=None, password=None, pkey=None):
        """Connect to host
        
        :raises: :mod:`pssh.exceptions.AuthenticationException` on authentication error
        :raises: :mod:`pssh.exceptions.UnknownHostException` on DNS resolution error
        :raises: :mod:`pssh.exceptions.ConnectionErrorException` on error connecting
        :raises: :mod:`pssh.exceptions.SSHException` on other undefined SSH errors
        """
        try:
            client.connect(host, username=user if user else self.user,
                           password=password if password else self.password,
                           port=port, pkey=pkey if pkey else self.pkey,
                           sock=sock, timeout=self.timeout,
                           allow_agent=self.allow_agent)
        except sock_gaierror, ex:
            logger.error("Could not resolve host '%s' - retry %s/%s",
                         host, retries, self.num_retries)
            while retries < self.num_retries:
                sleep(5)
                return self._connect(client, host, port, sock=sock,
                                     retries=retries+1)
            raise UnknownHostException("Unknown host %s - %s - retry %s/%s",
                                       host, str(ex.args[1]), retries,
                                       self.num_retries)
        except sock_error, ex:
            logger.error("Error connecting to host '%s:%s' - retry %s/%s",
                         self.host, self.port, retries, self.num_retries)
            while retries < self.num_retries:
                sleep(5)
                return self._connect(client, host, port, sock=sock,
                                     retries=retries+1)
            error_type = ex.args[1] if len(ex.args) > 1 else ex.args[0]
            raise ConnectionErrorException("Error connecting to host '%s:%s' - %s - retry %s/%s",
                                           self.host, self.port,
                                           str(error_type), retries, self.num_retries,)
        except paramiko.AuthenticationException, ex:
            msg = "Authentication error while connecting to %s:%s."
            raise AuthenticationException(msg, host, port)
        # SSHException is more general so should be below other types
        # of SSH failure
        except paramiko.SSHException, ex:
            msg = "General SSH error - %s" % (ex,)
            logger.error(msg)
            raise SSHException(msg, host, port)

    def exec_command(self, command, sudo=False, user=None,
                     shell=None,
                     use_shell=True, use_pty=True,
                     **kwargs):
        """Wrapper to :mod:`paramiko.SSHClient.exec_command`
        
        Opens a new SSH session with a new pty and runs command before yielding 
        the main gevent loop to allow other greenlets to execute.
        
        :param command: Cxommand to execute
        :type command: str
        :param sudo: (Optional) Run with sudo. Defaults to False
        :type sudo: bool
        :param user: (Optional) User to switch to via sudo to run command as. \
        Defaults to user running the python process
        :type user: str
        :param shell: (Optional) Shell override to use instead of user login \
        configured shell. For example ``shell='bash -c'``
        :param use_shell: (Optional) Force use of shell on/off. \
        Defaults to `True` for on
        :type use_shell: bool
        :param use_pty: (Optional) Enable/Disable use of pseudo terminal \
        emulation. This is required in vast majority of cases, exception \
        being where a shell is not used and stdout/stderr/stdin buffers \
        are not required. Defaults to ``True``
        :type use_pty: bool
        :param kwargs: (Optional) Keyword arguments to be passed to remote \
        command
        :type kwargs: dict
        :rtype: Tuple of `(channel, hostname, stdout, stderr, stdin)`. \
        Channel is the remote SSH channel, needed to ensure all of stdout has \
        been got, hostname is remote hostname the copy is to, stdout and \
        stderr are buffers containing command output.
        """
        channel = self.client.get_transport().open_session()
        if self.forward_ssh_agent:
            agent_handler = paramiko.agent.AgentRequestHandler(channel)
        if use_pty:
            channel.get_pty()
        if self.channel_timeout:
            channel.settimeout(self.channel_timeout)
        stdin = channel.makefile('wb')
        _stdout, _stderr = channel.makefile('rb'), \
                           channel.makefile_stderr('rb')
        stdout, stderr = self._read_output_buffer(_stdout,), \
                         self._read_output_buffer(_stderr,
                                                  prefix='\t[err]')
        for _char in ['\\', '"', '$', '`']:
            command = command.replace(_char, '\%s' % (_char,))
        shell = '$SHELL -c' if not shell else shell
        _command = ''
        if sudo and not user:
            _command = 'sudo -S '
        elif user:
            _command = 'sudo -u %s -S ' % (user,)
        if use_shell:
            _command += '%s "%s"' % (shell, command,)
        else:
            _command += '"%s"' % (command,)
        logger.debug("Running parsed command %s on %s", _command, self.host)
        channel.exec_command(_command, **kwargs)
        logger.debug("Command started")
        sleep(0)
        return channel, self.host, stdout, stderr, stdin

    def _read_output_buffer(self, output_buffer, prefix=''):
        """Read from output buffers and log to host_logger"""
        for line in output_buffer:
            output = line.strip().decode('utf8')
            host_logger.info("[%s]%s\t%s", self.host, prefix, output,)
            yield output

    def _make_sftp(self):
        """Make SFTP client from open transport"""
        transport = self.client.get_transport()
        transport.open_session()
        return paramiko.SFTPClient.from_transport(transport)

    def _mkdir(self, sftp, directory):
        """Make directory via SFTP channel
        
        :param sftp: SFTP client object
        :type sftp: :mod:`paramiko.SFTPClient`
        :param directory: Remote directory to create
        :type directory: str
        
        Catches and logs at error level remote IOErrors on creating directory.
        """
        try:
            sftp.mkdir(directory)
        except IOError, error:
            msg = "Error occured creating directory %s on %s - %s"
            logger.error(msg, directory, self.host, error)
            raise IOError(msg, directory, self.host, error)
        logger.debug("Creating remote directory %s", directory)
        return True

    def mkdir(self, sftp, directory):
        """Make directory via SFTP channel.
        
        Parent paths in the directory are created if they do not exist.
        
        :param sftp: SFTP client object
        :type sftp: :mod:`paramiko.SFTPClient`
        :param directory: Remote directory to create
        :type directory: str
        
        Catches and logs at error level remote IOErrors on creating directory.
        """
        try:
            parent_path, sub_dirs = directory.split(os.path.sep, 1)
        except ValueError:
            parent_path = directory.split(os.path.sep, 1)[0]
            sub_dirs = None
        if not parent_path and directory.startswith(os.path.sep):
            try:
                parent_path, sub_dirs = sub_dirs.split(os.path.sep, 1)
            except ValueError:
                return True
        try:
            sftp.stat(parent_path)
        except IOError:
            self._mkdir(sftp, parent_path)
        sftp.chdir(parent_path)
        if sub_dirs:
            return self.mkdir(sftp, sub_dirs)
        return True

    def _copy_dir(self, local_dir, remote_dir):
        """Call copy_file on every file in the specified directory, copying
        them to the specified remote directory."""
        file_list = os.listdir(local_dir)
        for file_name in file_list:
            local_path = os.path.join(local_dir, file_name)
            remote_path = os.path.join(remote_dir, file_name)
            self.copy_file(local_path, remote_path, recurse=True)

    def copy_file(self, local_file, remote_file, recurse=False):
        """Copy local file to host via SFTP/SCP
        
        Copy is done natively using SFTP/SCP version 2 protocol, no scp command \
        is used or required.
        
        :param local_file: Local filepath to copy to remote host
        :type local_file: str
        :param remote_file: Remote filepath on remote host to copy file to
        :type remote_file: str
        :param recurse: Whether or not to descend into directories recursively.
        :type recurse: bool
        
        :raises: :mod:`ValueError` when a directory is supplied to ``local_file`` \
        and ``recurse`` is not set
        """
        if os.path.isdir(local_file) and recurse:
            return self._copy_dir(local_file, remote_file)
        elif os.path.isdir(local_file) and not recurse:
            raise ValueError("Recurse must be true if local_file is a "
                             "directory.")
        sftp = self._make_sftp()
        try:
            destination = os.path.sep.join([_dir for _dir in remote_file.split(os.path.sep)
                           if _dir][:-1])
        except IndexError:
            destination = ''
        if remote_file.startswith(os.path.sep) or not destination:
            destination = os.path.sep + destination
        if os.path.sep in remote_file:
            self.mkdir(sftp, destination)
        sftp.chdir()
        try:
            sftp.put(local_file, remote_file)
        except Exception, error:
            logger.error("Error occured copying file %s to remote destination %s:%s - %s",
                         local_file, self.host, remote_file, error)
            raise error
        logger.info("Copied local file %s to remote destination %s:%s",
                    local_file, self.host, remote_file)
