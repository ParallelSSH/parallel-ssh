# flake8: noqa: F401

from warnings import warn

warn("Importing from pssh.pssh2_client is deprecated. Please update to "
     "from pssh.clients import ParallelSSHClient")

from .clients.native import ParallelSSHClient, logger
