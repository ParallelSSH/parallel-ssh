import os
from gevent import joinall
from datetime import datetime
from pssh.clients import ParallelSSHClient


with open('file_copy', 'wb') as fh:
    for _ in range(2000000):
        fh.write(b'asdfa')


fileinfo = os.stat('file_copy')
client = ParallelSSHClient(['localhost'])
now = datetime.now()
cmd = client.copy_file('file_copy', '/tmp/file_copy')
joinall(cmd, raise_error=True)
taken = datetime.now() - now
mb_size = fileinfo.st_size / (1024000.0)
rate = mb_size / taken.total_seconds()
print("File size %sMB transfered in %s, transfer rate %s MB/s" % (
    mb_size, taken, rate))
