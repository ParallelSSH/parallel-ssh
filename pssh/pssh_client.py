# flake8: noqa: F401

from warnings import warn

warn("Importing from pssh.pssh_client is deprecated. Please update to "
     "from pssh.clients import ParallelSSHClient for the default client, "
     "or pssh.clients.miko import ParallelSSHClient to continue using the "
     "paramiko client only instead.")

from .clients.miko import ParallelSSHClient, logger
