# flake8: noqa: F401

from warnings import warn

warn("Importing from pssh.ssh2_client is deprecated. Please update to "
     "from pssh.clients import SSHClient")

from .clients.native import SSHClient, logger
