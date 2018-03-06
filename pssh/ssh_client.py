# flake8: noqa: F401

from warnings import warn

warn("Importing from pssh.ssh2_client is deprecated. Please update to "
     "from pssh.clients import SSHClient for the default client, or "
     "from pssh.clients.miko import SSHClient to continue using the paramiko "
     "client only.")

from .clients.miko import SSHClient, logger
