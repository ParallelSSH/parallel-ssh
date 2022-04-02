import os
from gevent import joinall
from datetime import datetime
from pssh.clients import ParallelSSHClient


with open('file_copy', 'wb') as fh:
    # 200MB
    for _ in range(20055120):
        fh.write(b'asdfartkj\n')


fileinfo = os.stat('file_copy')
mb_size = fileinfo.st_size / (1024000.0)
client = ParallelSSHClient(['127.0.0.1'], timeout=1, num_retries=1)
print(f"Starting copy of {mb_size}MB file")
now = datetime.now()
cmd = client.copy_file('file_copy', '/tmp/file_copy')
joinall(cmd, raise_error=True)
taken = datetime.now() - now
rate = mb_size / taken.total_seconds()
print("File size %sMB transfered in %s, transfer rate %s MB/s" % (mb_size, taken, rate))
os.unlink('file_copy')
os.unlink('/tmp/file_copy')
