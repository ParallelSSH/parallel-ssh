parallel-ssh
============

Small wrapper library over paramiko that allows for parallel execution of SSH commands on remote hosts and executing simple single host commands over SSH

.. image:: https://api.travis-ci.org/pkittenis/parallel-ssh.png?branch=master
        :target: https://travis-ci.org/pkittenis/parallel-ssh

Installation
============
	sudo apt-get install libevent-dev
	pip install parallel-ssh

Usage Example
============

```python
from pssh import ParallelSSHClient
hosts = ['myhost1', 'myhost2']
client = ParallelSSHClient(hosts)
cmds = client.exec_command('ls -ltrh /tmp/aasdfasdf', sudo = True)
print [client.get_stdout(cmd) for cmd in cmds]
```
