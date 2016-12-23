parallel-ssh
============

Asynchronous parallel SSH client library.

Run commands via SSH over tens/hundreds/thousands+ number of servers asynchronously and with minimal system load on the client host.

.. image:: https://img.shields.io/pypi/v/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: Latest Version
.. image:: https://travis-ci.org/ParallelSSH/parallel-ssh.svg?branch=master
  :target: https://travis-ci.org/ParallelSSH/parallel-ssh
.. image:: https://coveralls.io/repos/ParallelSSH/parallel-ssh/badge.png?branch=master
  :target: https://coveralls.io/r/ParallelSSH/parallel-ssh?branch=master
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: http://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation

.. _`read the docs`: http://parallel-ssh.readthedocs.org/en/latest/

************
Installation
************

::

   pip install parallel-ssh

As of version ``0.93.0`` pip versions >= ``6.0.0`` are required for Python 2.6 compatibility. This limitation will be removed in ``1.0.0`` release which will drop ``2.6`` support.

*************
Usage Example
*************

See documentation on `read the docs`_ for more complete examples.

Run ``ls`` on two remote hosts in parallel with ``sudo``.

::

  from pssh import ParallelSSHClient
  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)
  output = client.run_command('ls -ltrh /tmp/', sudo=True)
  print(output)
  {'myhost1': {'exit_code': None, 'stdout': <generator>, 'stderr': <generator>, 'channel': <channel>, 'cmd' : <greenlet>, 'exception' : None},
   'myhost2': {'exit_code': None, 'stdout': <generator>, 'stderr': <generator>, 'channel': <channel>, 'cmd' : <greenlet>, 'exception' : None}}

Stdout and stderr buffers are available in output. Iterating on them can be used to get output as it becomes available. Iteration ends *only when command has finished*.

::

  for host in output:
     for line in output[host]['stdout']:
         print("Host %s - output: %s" % (host, line))
  Host myhost1 - output: drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
  Host myhost1 - output: <..>
  Host myhost2 - output: drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
  Host myhost2 - output: <..>

Exit codes become available once stdout/stderr is iterated on or ``client.join(output)`` is called.

::

  for host in output:
      print(output[host]['exit_code'])
  0
  0

Joining on the connection pool can be used to block and wait for all parallel commands to finish if output is not required. ::

  client.pool.join()

Similarly, if only exit codes are needed but not output ::

  output = client.run_command('exit 0')
  # Block and gather exit codes. Output variable is updated in-place
  client.join(output)
  print(output[client.hosts[0]]['exit_code'])
  0

There is a also host logger that can be enabled to log output from remote hosts. The helper function ``pssh.utils.enable_host_logger`` will enable host logging to stdout, for example ::

  import pssh.utils
  pssh.utils.enable_host_logger()
  output = client.run_command('uname')
  client.join(output)
  
  [localhost]	Linux


**************************
Frequently asked questions
**************************

:Q:
   Why should I use this module and not, for example, `fabric <https://github.com/fabric/fabric>`_?

:A:
   ParallelSSH's design goals and motivation are to provide a *library* for running *asynchronous* SSH commands in parallel with **no** load induced on the system by doing so with the intended usage being completely programmatic and non-interactive - Fabric provides none of these goals.
   
   Fabric is a port of `Capistrano <https://github.com/capistrano/capistrano>`_ from ruby to python. Its design goals are to provide a faithful port of capistrano with its `tasks` and `roles` to python with interactive command line being the intended usage. Its use as a library is non-standard and in `many <https://github.com/fabric/fabric/issues/521>`_ `cases <https://github.com/fabric/fabric/pull/674>`_ `just <https://github.com/fabric/fabric/pull/1215>`_ `plain <https://github.com/fabric/fabric/issues/762>`_ `broken <https://github.com/fabric/fabric/issues/1068>`_.
   
   Furthermore, its parallel commands use a combination of both threads and processes with extremely high CPU usage and system load while running. Fabric currently stands at over 6,000 lines of code, majority of which is untested, particularly if used as a library as opposed to less than 700 lines of code mostly consisting of documentation strings currently in `ParallelSSH` with over 80% code test coverage.

:Q:
 Is Windows supported?

:A:
 The library installs and works on Windows though not formally supported as unit tests are currently Posix system based.
 
 Pip versions >= 8.0 are required for binary package installation of `gevent` on Windows, a dependency of `ParallelSSH`. 
 
 Though `ParallelSSH` is pure python code and will run on any platform that has a working Python interpreter, its `gevent` dependency contains native code which either needs a binary package to be provided for the platform or to be built from source. Binary packages for `gevent` are provided for OSX, Linux and Windows platforms as of this time of writing.

:Q:
 Are SSH agents used?

:A:
 All available keys in a system configured SSH agent in addition to SSH keys in the user's home directory, `~/.ssh/id_dsa`, `~/.ssh/id_rsa` et al are automatically used by ParallelSSH. 
 
 Use of SSH agent can be disabled by creating a client as ``ParallelSSHClient(allow_agent=False)``. `See documentation <http://parallel-ssh.readthedocs.org/en/latest/>`_ for more information.

:Q:
  Can ParallelSSH forward my SSH agent?

:A:
  SSH agent forwarding, what ``ssh -A`` does on the command line, is supported and enabled by default. Creating an object as ``ParallelSSHClient(forward_ssh_agent=False)`` will disable that behaviour.

:Q:
  Is tunneling/proxying supported?

:A:
  Yes, `ParallelSSH` natively supports tunelling through an intermediate SSH server. Connecting to a remote host is accomplished via an SSH tunnel using the SSH's protocol direct TCP tunneling feature, using local port forwarding. This is done natively in python and tunnel connections are asynchronous like all other connections in the `ParallelSSH` library. For example, client -> proxy SSH server -> remote SSH destination.

  Use the ``proxy_host`` and ``proxy_port`` parameters to configure your proxy.

  >>> client = ParallelSSHClient(hosts, proxy_host='my_ssh_proxy_host')
  
  Note that while connections from the ParallelSSH client to the tunnel host are asynchronous, connections from the tunnel host to the remote destination(s) may not be, depending on the SSH server implementation. If the SSH server uses threading to implement its tunelling and that server is used to tunnel to a large number of remote destinations system load on the tunnel server will increase linearly according to number of remote hosts.

:Q:
  Is there a way to programmatically provide an SSH key?

:A:
  Yes, use the ``pkey`` parameter of the `ParallelSSHClient class <http://parallel-ssh.readthedocs.org/en/latest/#pssh.ParallelSSHClient>`_. There is a ``load_private_key`` helper function in ``pssh.utils`` that can be used to load any supported key type. For example::

    from pssh import ParallelSSHClient, utils
    client_key = utils.load_private_key('user.key')
    client = ParallelSSHClient(['myhost1', 'myhost2'], pkey=client_key)

:Q:
   Is there a user's group for feedback and discussion about ParallelSSH?

:A:
   There is a public `ParallelSSH Google group <https://groups.google.com/forum/#!forum/parallelssh>`_ setup for this purpose - both posting and viewing are open to the public.


********
SFTP/SCP
********

SFTP is supported (SCP version 2) natively, no ``scp`` command required.

For example to copy a local file to remote hosts in parallel::

  from pssh import ParallelSSHClient, utils
  utils.enable_logger(utils.logger)
  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)
  client.copy_file('../test', 'test_dir/test')
  client.pool.join()
  
  Copied local file ../test to remote destination myhost1:test_dir/test
  Copied local file ../test to remote destination myhost2:test_dir/test
