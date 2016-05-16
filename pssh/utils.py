# This file is part of parallel-ssh.

# Copyright (C) 2014- Panos Kittenis

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


"""Package containing static utility functions for parallel-ssh module."""


import logging
import gevent
from paramiko.rsakey import RSAKey
from paramiko.dsskey import DSSKey
from paramiko.ecdsakey import ECDSAKey
from paramiko import SSHException

host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger('pssh')

def enable_logger(_logger, level=logging.INFO):
    """Enables logging to stdout for given logger"""
    stream_handlers = [h for h in _logger.handlers
                       if isinstance(h, logging.StreamHandler)]
    if stream_handlers:
        logger.warning("Logger already has a StreamHandler attached")
        return
    handler = logging.StreamHandler()
    host_log_format = logging.Formatter('%(message)s')
    handler.setFormatter(host_log_format)
    _logger.addHandler(handler)
    _logger.setLevel(level)

def enable_host_logger():
    """Enable host logger for logging stdout from remote commands
    as it becomes available"""
    enable_logger(host_logger)

def load_private_key(_pkey):
    """Load private key from pkey file object or filename
    
    :param pkey: File object or file name containing private key
    :type pkey: file/str"""
    if not hasattr(_pkey, 'read'):
        _pkey = open(_pkey)
    for keytype in [RSAKey, DSSKey, ECDSAKey]:
        try:
            pkey = keytype.from_private_key(_pkey)
        except SSHException:
            _pkey.seek(0)
            continue
        else:
            return pkey
    logger.error("Failed to load private key using all available key types - giving up..")

# def enable_pssh_logger():
#     """Enable parallel-ssh's logger to stdout"""
#     enable_logger(logger)
