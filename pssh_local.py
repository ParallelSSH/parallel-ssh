# This file is part of parallel-ssh.

# Copyright (C) 2015 Panos Kittenis

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

"""Connect to SSH server on localhost,
attempt to perform an `ls` and copy a test file with both SSHClient
and ParallelSSHClient.
"""

from pssh import SSHClient, ParallelSSHClient
import logging

logger = logging.getLogger(__name__)

def _setup_logger(_logger):
    """Setup default logger"""
    _handler = logging.StreamHandler()
    log_format = logging.Formatter(
        '%(name)s - %(asctime)s - %(levelname)s - %(message)s')
    _handler.setFormatter(log_format)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.DEBUG)
    
def test():
    """Perform ls and copy file with SSHClient on localhost"""
    client = SSHClient('localhost')
    channel, host, stdout, stderr = client.exec_command('ls -ltrh')
    for line in stdout:
        print line.strip()
    client.copy_file('../test', 'test_dir/test')

def test_parallel():
    """Perform ls and copy file with ParallelSSHClient on localhost"""
    client = ParallelSSHClient(['localhost', 'localhost'])
    output = client.run_command('ls -ltrh')
    print output
    # cmds = client.copy_file('../test', 'test_dir/test')
    # client.pool.join()

if __name__ == "__main__":
    _setup_logger(logger)
    # test()
    test_parallel()
