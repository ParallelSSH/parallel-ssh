# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2022 Panos Kittenis and contributors.
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
                 'alias', 'num_retries', 'retry_delay', 'timeout', 'identity_auth',
                 'proxy_host', 'proxy_port', 'proxy_user', 'proxy_password', 'proxy_pkey',
                 'keepalive_seconds', 'ipv6_only', 'cert_file', 'auth_thread_pool', 'gssapi_auth',
                 'gssapi_server_identity', 'gssapi_client_identity', 'gssapi_delegate_credentials',
                 'forward_ssh_agent',
                 )

    def __init__(self, user=None, port=None, password=None, private_key=None,
                 allow_agent=None, alias=None, num_retries=None, retry_delay=None, timeout=None,
                 identity_auth=None,
                 proxy_host=None, proxy_port=None, proxy_user=None, proxy_password=None,
                 proxy_pkey=None,
                 keepalive_seconds=None,
                 ipv6_only=None,
                 cert_file=None,
                 auth_thread_pool=True,
                 gssapi_auth=False,
                 gssapi_server_identity=None,
                 gssapi_client_identity=None,
                 gssapi_delegate_credentials=False,
                 forward_ssh_agent=False,
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
        :param alias: Use an alias for this host.
        :type alias: str or int
        :param num_retries: Number of retry attempts before giving up on connection
          and SSH operations.
        :type num_retries: int
        :param retry_delay: Delay in seconds between retry attempts.
        :type retry_delay: int or float
        :param timeout: Timeout value for connection and SSH sessions in seconds.
        :type timeout: int or float
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
        :param ipv6_only: Use IPv6 addresses only.
        :type ipv6_only: bool
        :param cert_file: Certificate file for authentication (pssh.clients.ssh only)
        :type cert_file: str
        :param auth_thread_pool: Enable/Disable use of thread pool for authentication.
        :type auth_thread_pool: bool
        :param forward_ssh_agent: Currently unused.
        :type forward_ssh_agent: bool
        :param gssapi_server_identity: Set GSSAPI server identity. (pssh.clients.ssh only)
        :type gssapi_server_identity: str
        :param gssapi_server_identity: Set GSSAPI client identity. (pssh.clients.ssh only)
        :type gssapi_server_identity: str
        :param gssapi_delegate_credentials: Enable/disable server credentials
          delegation. (pssh.clients.ssh only)
        :type gssapi_delegate_credentials: bool
        """
        self.user = user
        self.port = port
        self.password = password
        self.private_key = private_key
        self.allow_agent = allow_agent
        self.alias = alias
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
        self.ipv6_only = ipv6_only
        self.cert_file = cert_file
        self.auth_thread_pool = auth_thread_pool
        self.forward_ssh_agent = forward_ssh_agent
        self.gssapi_auth = gssapi_auth
        self.gssapi_server_identity = gssapi_server_identity
        self.gssapi_client_identity = gssapi_client_identity
        self.gssapi_delegate_credentials = gssapi_delegate_credentials
        self._sanity_checks()

    def _sanity_checks(self):
        if self.user is not None and not isinstance(self.user, str):
            raise ValueError("Username %s is not a string" % (self.user,))
        if self.port is not None and not isinstance(self.port, int):
            raise ValueError("Port %s is not an integer" % (self.port,))
        if self.password is not None and not isinstance(self.password, str):
            raise ValueError("Password %s is not a string" % (self.password,))
        if self.alias is not None and not isinstance(self.alias, str):
            raise ValueError("Alias %s is not a string" % (self.alias,))
        if self.private_key is not None and not (
                isinstance(self.private_key, str) or isinstance(self.private_key, bytes)
        ):
            raise ValueError("Private key %s is not a string or bytes" % (self.private_key,))
        if self.allow_agent is not None and not isinstance(self.allow_agent, bool):
            raise ValueError("Allow agent %s is not a boolean" % (self.allow_agent,))
        if self.num_retries is not None and not isinstance(self.num_retries, int):
            raise ValueError("Num retries %s is not an integer" % (self.num_retries,))
        if self.timeout is not None and not \
                (isinstance(self.timeout, int) or isinstance(self.timeout, float)):
            raise ValueError("Timeout %s is not an integer" % (self.timeout,))
        if self.retry_delay is not None and not \
                (isinstance(self.retry_delay, int) or isinstance(self.retry_delay, float)):
            raise ValueError("Retry delay %s is not a number" % (self.retry_delay,))
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
        if self.proxy_pkey is not None and not (
                isinstance(self.proxy_pkey, str) or isinstance(self.proxy_pkey, bytes)
        ):
            raise ValueError("Proxy pkey %s is not a string or bytes" % (self.proxy_pkey,))
        if self.keepalive_seconds is not None and not isinstance(self.keepalive_seconds, int):
            raise ValueError("Keepalive seconds %s is not an integer" % (self.keepalive_seconds,))
        if self.ipv6_only is not None and not isinstance(self.ipv6_only, bool):
            raise ValueError("IPv6 only %s is not a boolean value" % (self.ipv6_only,))
        if self.cert_file is not None and not (
                isinstance(self.cert_file, str) or isinstance(self.cert_file, bytes)
        ):
            raise ValueError("Cert file %s is not a string or bytes", self.cert_file)
        if self.forward_ssh_agent is not None and not isinstance(self.forward_ssh_agent, bool):
            raise ValueError("Forward SSH agent %s is not a bool", self.forward_ssh_agent)
        if self.gssapi_auth is not None and not isinstance(self.gssapi_auth, bool):
            raise ValueError("GSSAPI auth %s is not a bool", self.gssapi_auth)
        if self.gssapi_server_identity is not None and not isinstance(self.gssapi_server_identity, str):
            raise ValueError("GSSAPI server identity %s is not a string", self.gssapi_server_identity)
        if self.gssapi_client_identity is not None and not isinstance(self.gssapi_client_identity, str):
            raise ValueError("GSSAPI client identity %s is not a string", self.gssapi_client_identity)
        if self.gssapi_delegate_credentials is not None and not isinstance(self.gssapi_delegate_credentials, bool):
            raise ValueError("GSSAPI delegate credentials %s is not a bool", self.gssapi_delegate_credentials)
