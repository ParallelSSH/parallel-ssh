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
import os
from paramiko.rsakey import RSAKey
from paramiko.dsskey import DSSKey
from paramiko.ecdsakey import ECDSAKey
from paramiko import SSHException, SSHConfig

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

def read_openssh_config(_host, config_file=None):
    """Parses user's OpenSSH config for per hostname configuration for
    hostname, user, port and private key values

    :param _host: Hostname to lookup in config"""
    _ssh_config_file = config_file if config_file else \
      os.path.sep.join([os.path.expanduser('~'),
                        '.ssh', 'config'])
    # Load ~/.ssh/config if it exists to pick up username
    # and host address if set
    if not os.path.isfile(_ssh_config_file):
        return
    ssh_config = SSHConfig()
    ssh_config.parse(open(_ssh_config_file))
    host_config = ssh_config.lookup(_host)
    host = (host_config['hostname'] if
            'hostname' in host_config
            else _host)
    user = host_config['user'] if 'user' in host_config else None
    port = int(host_config['port']) if 'port' in host_config else 22
    pkey = None
    # Try configured keys, pick first one that loads
    if 'identityfile' in host_config:
        for file_name in host_config['identityfile']:
            pkey = load_private_key(file_name)
            if pkey:
                break
    return host, user, port, pkey

# def enable_pssh_logger():
#     """Enable parallel-ssh's logger to stdout"""
#     enable_logger(logger)
