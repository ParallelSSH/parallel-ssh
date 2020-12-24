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


"""Host specific configuration."""


class HostConfig(object):
    """Host configuration for ParallelSSHClient.

    Used to hold individual configuration for each host in ParallelSSHClient host list.
    """
    __slots__ = ('user', 'port', 'password', 'private_key', 'allow_agent',
                 'num_retries', 'retry_delay', 'timeout', 'identity_auth',
                 'proxy_host', 'proxy_port', 'proxy_user', 'proxy_password', 'proxy_pkey',
                 'keepalive_seconds',
                 )

    def __init__(self, user=None, port=None, password=None, private_key=None,
                 allow_agent=None, num_retries=None, retry_delay=None, timeout=None,
                 identity_auth=None,
                 proxy_host=None, proxy_port=None, proxy_user=None, proxy_password=None,
                 proxy_pkey=None,
                 keepalive_seconds=None,
                 ):
        """
        :param user: Username to login as.
        :type user: str
        :param port: Port number.
        :type port: int
        :param password: Password to login with.
        :type password: str
        :param private_key: Private key file to use for authentication.
        :type private_key: str
        :param allow_agent: Enable/disable SSH agent authentication.
        :type allow_agent: bool
        :param num_retries: Number of retry attempts before giving up on connection
          and SSH operations.
        :type num_retries: int
        :param retry_delay: Delay in seconds between retry attempts.
        :type retry_delay: int
        :param timeout: Timeout value for connection and SSH sessions in seconds.
        :type timeout: int
        :param identity_auth: Enable/disable identity file authentication under user's
          home directory (~/.ssh).
        :type identity_auth: bool
        :param proxy_host: Proxy SSH host to use for connecting to target SSH host.
          client -> proxy_host -> SSH host
        :type proxy_host: str
        :param proxy_port: Port for proxy host.
        :type proxy_port: int
        :param proxy_user: Username for proxy host.
        :type proxy_user: str
        :param proxy_password: Password for proxy host.
        :type proxy_password: str
        :param proxy_pkey: Private key for proxy host.
        :type proxy_pkey: str
        :param keepalive_seconds: Seconds between keepalive packets being sent.
          0 to disable.
        :type keepalive_seconds: int
        """
        self.user = user
        self.port = port
        self.password = password
        self.private_key = private_key
        self.allow_agent = allow_agent
        self.num_retries = num_retries
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.identity_auth = identity_auth
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password
        self.proxy_pkey = proxy_pkey
        self.keepalive_seconds = keepalive_seconds
        self._sanity_checks()

    def _sanity_checks(self):
        if self.user is not None and not isinstance(self.user, str):
            raise ValueError("Username %s is not a string" % (self.user,))
        if self.port is not None and not isinstance(self.port, int):
            raise ValueError("Port %s is not an integer" % (self.port,))
        if self.password is not None and not isinstance(self.password, str):
            raise ValueError("Password %s is not a string" % (self.password,))
        if self.private_key is not None and not isinstance(self.private_key, str):
            raise ValueError("Private key %s is not a string" % (self.private_key,))
        if self.allow_agent is not None and not isinstance(self.allow_agent, bool):
            raise ValueError("Allow agent %s is not a boolean" % (self.allow_agent,))
        if self.num_retries is not None and not isinstance(self.num_retries, int):
            raise ValueError("Num retries %s is not an integer" % (self.num_retries,))
        if self.timeout is not None and not isinstance(self.timeout, int):
            raise ValueError("Timeout %s is not an integer" % (self.timeout,))
        if self.retry_delay is not None and not isinstance(self.retry_delay, int):
            raise ValueError("Retry delay %s is not an integer" % (self.retry_delay,))
        if self.identity_auth is not None and not isinstance(self.identity_auth, bool):
            raise ValueError("Identity auth %s is not a boolean" % (self.identity_auth,))
        if self.proxy_host is not None and not isinstance(self.proxy_host, str):
            raise ValueError("Proxy host %s is not a string" % (self.proxy_host,))
        if self.proxy_port is not None and not isinstance(self.proxy_port, int):
            raise ValueError("Proxy port %s is not an integer" % (self.proxy_port,))
        if self.proxy_user is not None and not isinstance(self.proxy_user, str):
            raise ValueError("Proxy user %s is not a string" % (self.proxy_user,))
        if self.proxy_password is not None and not isinstance(self.proxy_password, str):
            raise ValueError("Proxy password %s is not a string" % (self.proxy_password,))
        if self.proxy_pkey is not None and not isinstance(self.proxy_pkey, str):
            raise ValueError("Proxy pkey %s is not a string" % (self.proxy_pkey,))
        if self.keepalive_seconds is not None and not isinstance(self.keepalive_seconds, int):
            raise ValueError("Keepalive seconds %s is not an integer" % (self.keepalive_seconds,))
