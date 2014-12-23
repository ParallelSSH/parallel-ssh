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

**************
Usage Examples
**************

See documentation on `read the docs`_ for more complete examples.

Run `ls` on two remote hosts in parallel.

>>> from pssh import ParallelSSHClient
>>> hosts = ['myhost1', 'myhost2']
>>> client = ParallelSSHClient(hosts)
>>> output = client.run_command('ls -ltrh /tmp/aasdfasdf', sudo=True)
>>> for host in output: print output
[localhost]     drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
{'localhost': {'exit_code': 0, 'stdout': <generator>, 'stderr': <generator>, 'channel': channel}}

**************************
Frequently asked questions
**************************

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
  >>> my_key = paramiko.RSAKey.from_private_key_file(my_rsa_key)
  >>> client = ParallelSSHClient(pkey=my_key)

:Q:
   Why should I use this module and not, for example, `fabric <https://github.com/fabric/fabric>`_?

:A:
   Fabric is a port of `capistrano <https://github.com/capistrano/capistrano>`_ from ruby to python. Its design goals are to provide a faithful port of capistrano with capistrano's `tasks` and `roles` to python with interactive command line being the intended usage - its use as a library is non-standard and in many cases just plain broken.
   Furthermore, its parallel commands use a combination of both threads and processes with extremely high CPU usage while its running. Fabric currently stands at more than 130,000 lines of code, a large proportion of which is untested, particularly if used as a library as opposed to less than 700 currently in `ParallelSSH` with over 70% code test coverage.
   ParallelSSH's design goals are to provide a *library* for running *asynchronous* SSH commands with **minimal** load induced on the system by doing so with the inteded usage being completely programmatic and non-interactive - Fabric provides none of these goals.

********
SFTP/SCP
********

SFTP is supported (scp version 2) natively, no scp command used.

For example to copy a local file to remote hosts in parallel

>>> from pssh import ParallelSSHClient
>>> hosts = ['myhost1', 'myhost2']
>>> client = ParallelSSHClient(hosts)
>>> client.copy_file('../test', 'test_dir/test')
>>> client.pool.join()
Copied local file ../test to remote destination myhost1:test_dir/test
Copied local file ../test to remote destination myhost2:test_dir/test
