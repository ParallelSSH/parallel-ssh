#!/usr/bin/env python

"""Module containing wrapper classes over paramiko.SSHClient
See SSHClient and ParallelSSHClient"""

import gevent.pool
from gevent import monkey
monkey.patch_all()
import paramiko
import os
import logging
import socket

host_logger = logging.getLogger('host_logging')
handler = logging.StreamHandler()
host_log_format = logging.Formatter('%(message)s')
handler.setFormatter(host_log_format)
host_logger.addHandler(handler)
host_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


def _setup_logger(_logger):
    """Setup default logger"""
    _handler = logging.StreamHandler()
    log_format = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')
    _handler.setFormatter(log_format)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)


class UnknownHostException(Exception):
    """Raised when a host is unknown (dns failure)"""
    pass


class ConnectionErrorException(Exception):
    """Raised on error connecting (connection refused/timed out)"""
    pass


class AuthenticationException(Exception):
    """Raised on authentication error (user/password/ssh key error"""
    pass


class SSHClient(object):
    """Wrapper class over paramiko.SSHClient with sane defaults"""

    def __init__(self, host,
                 user=None,
                 password=None, port=None):
        """Connect to host honoring any user set configuration in ~/.ssh/config
         or /etc/ssh/ssh_config
        :type: str
        :param host: Hostname to connect to
        :type str:
        :param user: (Optional) User to login as. Defaults to logged in user or
         user from ~/.ssh/config if set
        :throws: ssh_client.AuthenticationException on authentication error
        :throws: ssh_client.UnknownHostException on DNS resolution error
        :throws: ssh_client.ConnectionErrorException on error connecting"""
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
        if user:
            user = user
        else:
            user = _user
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        self.client = client
        self.channel = None
        self.user = user
        self.password = password
        self.port = port if port else 22
        self.host = resolved_address
        self._connect()

    def _connect(self):
        """Connect to host, throw UnknownHost exception on DNS errors"""
        try:
            self.client.connect(self.host, username=self.user,
                                password=self.password, port=self.port)
        except socket.gaierror, e:
            logger.error("Could not resolve host '%s'", self.host,)
            raise UnknownHostException("%s - %s" % (str(e.args[1]),
                                                    self.host,))
        except socket.error, e:
            logger.error("Error connecting to host '%s'", self.host,)
            raise ConnectionErrorException("%s for host '%s'" % (str(e.args[1]),
                                                                 self.host,))
        except paramiko.AuthenticationException, e:
            raise AuthenticationException(e)

    def exec_command(self, command, sudo=False, **kwargs):
        """Wrapper to paramiko.SSHClient.exec_command"""
        channel = self.client.get_transport().open_session()
        channel.get_pty()
        (_, stdout, stderr) = (channel.makefile('wb'), channel.makefile('rb'),
                               channel.makefile_stderr('rb'))
        if sudo:
            command = 'sudo -S bash -c "%s"' % command.replace('"', '\\"')
        else:
            command = 'bash -c "%s"' % command.replace('"', '\\"')
        logger.debug("Running command %s on %s", command, self.host)
        channel.exec_command(command, **kwargs)
        logger.debug("Command finished executing")
        while not (channel.recv_ready() or channel.closed):
            gevent.sleep(.2)
        return channel, self.host, stdout, stderr

class ParallelSSHClient(object):
    """Uses SSHClient, runs command on multiple hosts in parallel"""

    def __init__(self, hosts,
                 user=None, password=None, port=None,
                 pool_size=10):
        """Connect to hosts
        :type: list(str)
        :param hosts: Hosts to connect to
        :type: int
        :param pool_size: Pool size - how many commands to run in parallel
        :type str:
        :param user: (Optional) User to login as. Defaults to logged in user or
        user from ~/.ssh/config if set
        :type str:
        :param password: (Optional) Password to use for login
        :throws: paramiko.AuthenticationException on authentication error
        :throws: ssh_client.UnknownHostException on DNS resolution error
        :throws: ssh_client.ConnectionErrorException on error connecting"""
        self.pool = gevent.pool.Pool(size=pool_size)
        self.pool_size = pool_size
        self.hosts = hosts
        self.user = user
        self.password = password
        self.port = port
        # To hold host clients
        self.host_clients = dict((host, None) for host in hosts)

    def exec_command(self, *args, **kwargs):
        """Run command on all hosts in parallel, honoring self.pool_size"""
        return [self.pool.spawn(self._exec_command, host, *args, **kwargs)
                for host in self.hosts]

    def _exec_command(self, host, *args, **kwargs):
        """Make SSHClient, run command on host"""
        if not self.host_clients[host]:
            self.host_clients[host] = SSHClient(host, user=self.user,
                                                password=self.password,
                                                port=self.port)
        return self.host_clients[host].exec_command(*args, **kwargs)

    def get_stdout(self, greenlet):
        """Print stdout from greenlet and return exit code for host"""
        channel, host, stdout, stderr = greenlet.get()
        for line in stdout:
            host_logger.info("[%s]\t%s", host, line.strip(),)
        for line in stderr:
            host_logger.info("[%s] [err] %s", host, line.strip(),)
        channel.close()
        return {host: {'exit_code': channel.recv_exit_status()}}


def test():
    client = SSHClient('localhost')
    channel, host, stdout, stderr = client.exec_command('ls -ltrh')
    for line in stdout:
        print line.strip()

if __name__ == "__main__":
    _setup_logger(logger)
    test()
