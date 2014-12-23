parallel-ssh
============

Small wrapper library over paramiko that allows for parallel execution of SSH commands on remote hosts and executing simple single host commands over SSH.

parallel-ssh uses asychronous network requests - there is *no* multi-threading or multi-processing used.

This is a *requirement* for commands on many (hundreds/thousands/hundreds of thousands) of hosts which would grind a system to a halt simply by having so many processes/threads all wanting to execute if done with multi-threading/processing.

.. image:: https://api.travis-ci.org/pkittenis/parallel-ssh.png?branch=master
  :target: https://travis-ci.org/pkittenis/parallel-ssh
.. image:: https://coveralls.io/repos/pkittenis/parallel-ssh/badge.png?branch=master
  :target: https://coveralls.io/r/pkittenis/parallel-ssh?branch=master
.. image:: https://pypip.in/version/parallel-ssh/badge.png
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: version
.. image:: https://pypip.in/download/parallel-ssh/badge.png
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: downloads
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: http://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation

.. _`read the docs`: http://parallel-ssh.readthedocs.org/en/latest/

************
Installation
************

::

   $ pip install parallel-ssh

*************
Usage Example
*************

See documentation on `read the docs`_ for more complete examples.

Run `ls` on two remote hosts in parallel.

>>> from pssh import ParallelSSHClient
>>> hosts = ['myhost1', 'myhost2']
>>> client = ParallelSSHClient(hosts)
>>> output = client.run_command('ls -ltrh /tmp/', sudo=True)
>>> print output
{'myhost1': {'exit_code': 0, 'stdout': <generator>, 'stderr': <generator>, 'channel': <channel>, 'cmd' : <greenlet>},
 'myhost2': {'exit_code': 0, 'stdout': <generator>, 'stderr': <generator>, 'channel': <channel>, 'cmd' : <greenlet>}}

Stdout and stderr buffers are available in output. Iterating on them can be used to get output as it becomes available.

>>> for host in output:
>>>     for line in output[host]['stdout']:
>>>         print "Host %s - output: %s" % (host, line)
Host myhost1 - output: drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
Host myhost2 - output: drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx

**************************
Frequently asked questions
**************************

:Q:
   Why should I use this module and not, for example, `fabric <https://github.com/fabric/fabric>`_?

:A:
   Fabric is a port of `Capistrano <https://github.com/capistrano/capistrano>`_ from ruby to python. Its design goals are to provide a faithful port of capistrano with its `tasks` and `roles` to python with interactive command line being the intended usage. Its use as a library is non-standard and in `many <https://github.com/fabric/fabric/issues/521>`_ `cases <https://github.com/fabric/fabric/pull/674>`_ `just <https://github.com/fabric/fabric/pull/1215>`_ `plain <https://github.com/fabric/fabric/issues/762>`_ `broken <https://github.com/fabric/fabric/issues/1068>`_.
   
   Furthermore, its parallel commands use a combination of both threads and processes with extremely high CPU usage and system load while running. Fabric currently stands at over 6,000 lines of code, majority of which is untested, particularly if used as a library as opposed to less than 700 lines of code currently in `ParallelSSH` with over 80% code test coverage.
   
   ParallelSSH's design goals and motivation are to provide a *library* for running *asynchronous* SSH commands in parallel with **no** load induced on the system by doing so with the intended usage being completely programmatic and non-interactive - Fabric provides none of these goals.

:Q:
 Are SSH agents used?

:A:
 All available keys in a running SSH agent in addition to SSH keys in the user's home directory, `~/.ssh/id_dsa`, `~/.ssh/id_rsa` et al are automatically used by ParallelSSH.

:Q:
  Can ParallelSSH forward my SSH agent?

:A:
  SSH agent forwarding, what `ssh -A` does on the command line, is supported and enabled by default. Creating an object as `ParallelSSH(forward_ssh_agent=False)` will disable that behaviour.

:Q:
  Is proxying supported?

:A:
  ParallelSSH supports proxies as defined in SSH's `ProxyCommand` configuration in `~/.ssh/config`. For example, the following entry in `~/.ssh/config` causes ParallelSSH to use host `bastion` as a proxy for host `target`. See the `SSH manual page <http://unixhelp.ed.ac.uk/CGI/man-cgi?ssh+1>`_ for more information on `ProxyCommand`.

  ::

   Host target
     ProxyCommand ssh bastion -W %h:%p

:Q:
  Is there a way to programmatically provide an SSH key?

:A:
  Yes, use the `pkey` parameter of the `ParallelSSHClient class <http://parallel-ssh.readthedocs.org/en/latest/#pssh.ParallelSSHClient>`_. For example:

  >>> import paramiko
  >>> client_key = paramiko.RSAKey.from_private_key_file('user.key')
  >>> client = ParallelSSHClient(['myhost1', 'myhost2'], pkey=client_key)

********
SFTP/SCP
********

SFTP is supported (SCP version 2) natively, no `scp` command required.

For example to copy a local file to remote hosts in parallel

>>> from pssh import ParallelSSHClient
>>> hosts = ['myhost1', 'myhost2']
>>> client = ParallelSSHClient(hosts)
>>> client.copy_file('../test', 'test_dir/test')
>>> client.pool.join()
Copied local file ../test to remote destination myhost1:test_dir/test
Copied local file ../test to remote destination myhost2:test_dir/test
