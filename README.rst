parallel-ssh
============

Small wrapper library over paramiko that allows for parallel execution of SSH commands on remote hosts and executing simple single host commands over SSH.

parallel-ssh uses asychronous network requests, there is _no_ multi-threading or multi-processing used. This is a _requirement_ for commands on many (hundreds) of hosts which would grind a system to a halt simply by having so many processes/threads all wanting to execute if done with multi-threading/processing.

.. image:: https://api.travis-ci.org/pkittenis/parallel-ssh.png?branch=master
	:target: https://travis-ci.org/pkittenis/parallel-ssh

************
Installation
************
To install gevent you need the libevent-dev package installed. Instructions below are for apt-get systems, substitute with your own package manager if necessary.

::

	$ sudo apt-get install libevent-dev
	$ pip install parallel-ssh

*************
Usage Example
*************

>>> from pssh import ParallelSSHClient
>>> hosts = ['myhost1', 'myhost2']
>>> client = ParallelSSHClient(hosts)
>>> cmds = client.exec_command('ls -ltrh /tmp/aasdfasdf', sudo = True)
>>> print [client.get_stdout(cmd) for cmd in cmds]
[localhost]     drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
[{'localhost': {'exit_code': 0}}]


************
SFTP support
************

SFTP is supported (scp version 2 protocol) natively, no scp command used.

For example to copy a local file to remote hosts in parallel

>>> from pssh import ParallelSSHClient
>>> hosts = ['myhost1', 'myhost2']
>>> client = ParallelSSHClient(hosts)
>>> client.copy_file('../test', 'test_dir/test')
>>> client.pool.join()
Copied local file ../test to remote destination myhost1:test_dir/test
Copied local file ../test to remote destination myhost2:test_dir/test
