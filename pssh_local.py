from pssh import SSHClient, ParallelSSHClient
import logging

logger = logging.getLogger(__name__)

def _setup_logger(_logger):
    """Setup default logger"""
    _handler = logging.StreamHandler()
    log_format = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')
    _handler.setFormatter(log_format)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.DEBUG)
    
def test():
    client = SSHClient('localhost')
    channel, host, stdout, stderr = client.exec_command('ls -ltrh')
    for line in stdout:
        print line.strip()
    client.copy_file('../test', 'test_dir/test')

def test_parallel():
    client = ParallelSSHClient(['localhost'])
    cmds = client.exec_command('ls -ltrh')
    output = [client.get_stdout(cmd, return_buffers=True) for cmd in cmds]
    print output
    cmds = client.copy_file('../test', 'test_dir/test')
    client.pool.join()

if __name__ == "__main__":
    _setup_logger(logger)
    test()
    test_parallel()
