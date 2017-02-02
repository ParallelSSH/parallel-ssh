============
parallel-ssh
============

Asynchronous parallel SSH client library.

Run SSH commands over many - hundreds/hundreds of thousands - number of servers asynchronously and with minimal system load on the client host.

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

.. contents:: Table of Contents

************
Installation
************

::

   pip install parallel-ssh

As of version ``0.93.0`` ``pip`` version >= ``6.0.0`` is required for Python 2.6 compatibility with latest versions of gevent which have dropped 2.6 support. This limitation will be removed post ``1.0.0`` releases which will deprecate ``2.6`` support.

To upgrade ``pip`` run the following - use of ``virtualenv`` is recommended so as not to override system provided packages::

  pip install -U pip
  pip install parallel-ssh

*************
Usage Example
*************

See documentation on `read the docs`_ for more complete examples.

Run ``ls`` on two remote hosts in parallel with ``sudo``.

::

  from pprint import pprint
  from pssh.pssh_client import ParallelSSHClient

  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)
  output = client.run_command('ls -ltrh /tmp/', sudo=True)
  pprint(output)
  {'myhost1':
        host=myhost1
	cmd=<Greenlet>
	channel=<channel>
	stdout=<generator>
	stderr=<generator>
	stdin=<channel>
	exception=None
   'myhost2':
        <..>
  }

Standard output buffers are available in output object. Iterating on them can be used to get output as it becomes available. Iteration ends *only when command has finished*, though it may be interrupted and resumed at any point.

`Host output <http://parallel-ssh.readthedocs.io/en/latest/output.html>`_ attributes are available in per-host output dictionary, for example ``output['myhost1'].stdout``.

::

  for host in output:
     for line in output[host].stdout:
         pprint("Host %s - output: %s" % (host, line))
  Host myhost1 - output: drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
  Host myhost1 - output: <..>
  Host myhost2 - output: drwxr-xr-x  6 xxx xxx 4.0K Jan  1 00:00 xxx
  Host myhost2 - output: <..>

Exit codes become available once output is iterated on to completion *or* ``client.join(output)`` is called.

::

  for host in output:
      print(output[host].exit_code)
  0
  0

The client's ``join`` function can be used to block and wait for all parallel commands to finish::

  client.join(output)

Similarly, output and exit codes are available after ``client.join`` is called::

  output = client.run_command('exit 0')
  # Block and gather exit codes. Output is updated in-place
  client.join(output)
  pprint(output.values()[0].exit_code)
  0
  # Output is available
  for line in output.values()[0].stdout:
      pprint(line)
  <..stdout..>

.. note::

  In versions prior to ``1.0.0`` only, ``client.join`` would consume standard output.

There is also a built in host logger that can be enabled to log output from remote hosts. The helper function ``pssh.utils.enable_host_logger`` will enable host logging to stdout, for example ::

  import pssh.utils
  pssh.utils.enable_host_logger()
  client.join(client.run_command('uname'))
  
  [localhost]	Linux

*****************
Design And Goals
*****************

``ParallelSSH``'s design goals and motivation are to provide a *library* for running *asynchronous* SSH commands in parallel with little to no load induced on the system by doing so with the intended usage being completely programmatic and non-interactive.

To meet these goals, API driven solutions are preferred first and foremost. This frees up the developer to drive the library via any method desired, be that environment variables, CI driven tasks, command line tools, existing OpenSSH or new configuration files, from within an application et al.

********
Scaling
********

Some guide lines on scaling ``ParallelSSH`` client and pool size numbers.

In general, long lived commands with little or no output *gathering* will scale better. Pool sizes in the multiple thousands have been used successfully with little CPU overhead in the single process running them in these use cases.

Conversely, many short lived commands with output gathering will not scale as well. In this use case, smaller pool sizes in the hundreds are likely to perform better with regards to CPU overhead in the (g)event loop. Multiple processes, each with its own event loop, may be used to scale this use case further as CPU overhead allows.

Gathering is highlighted here as output generation does not affect scaling. Only when output is gathered either over multiple still running commands, or while more commands are being triggered, is overhead increased.

Technical Details
******************

To understand why this is, consider that in co-operative multi tasking, which is being used in this project via the ``gevent`` module, a co-routine (greenlet) needs to ``yield`` the event loop to allow others to execute - *co-operation*. When one co-routine is constantly grabbing the event loop in order to gather output, or when co-routines are constantly trying to start new short-lived commands, it causes overhead with other co-routines that also want to use the event loop.

This manifests itself as increased CPU usage in the process running the event loop and reduced performance with regards to scaling improvements from increasing pool size.

On the other end of the spectrum, long lived remote commands that generate *no* output only need the event loop at the start, when they are establishing connections, and at the end, when they are finished and need to gather exit codes, which results in practically zero CPU overhead at any time other than start or end of command execution.

Output *generation* is done remotely and has no effect on the event loop until output is gathered - output buffers are iterated on. Only at that point does the event loop need to be held.

********
SFTP/SCP
********

SFTP is supported (SCP version 2) natively, no ``scp`` command required.

For example to copy a local file to remote hosts in parallel::

  from pssh import ParallelSSHClient, utils
  from gevent import joinall

  utils.enable_logger(utils.logger)
  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)
  greenlets = client.copy_file('../test', 'test_dir/test')
  joinall(greenlets, raise_error=True)
  
  Copied local file ../test to remote destination myhost1:test_dir/test
  Copied local file ../test to remote destination myhost2:test_dir/test

There is similar capability to copy remote files to local ones suffixed with the host's name with the ``copy_remote_file`` function.

Directory recursion is supported in both cases via the ``recurse`` parameter - defaults to off.

See `copy_file <http://parallel-ssh.readthedocs.io/en/latest/pssh_client.html#pssh.pssh_client.ParallelSSHClient.copy_file>`_ and `copy_remote_file <http://parallel-ssh.readthedocs.io/en/latest/pssh_client.html#pssh.pssh_client.ParallelSSHClient.copy_remote_file>`_ documentation for more examples.

**************************
Frequently asked questions
**************************

:Q:
   Why should I use this library and not, for example, `fabric <https://github.com/fabric/fabric>`_?

:A:
   In short, the tools are intended for different use cases.

   ``ParallelSSH`` satisfies uses cases for a parallel SSH client library that scales well over hundreds to hundreds of thousands of hosts - per `Design And Goals`_ - a use case that is very common on cloud platforms and virtual machine automation. It would be best used where it is a good fit for the use case at hand.

   Fabric and tools like it on the other hand are not well suited to such use cases, for many reasons, performance and differing design goals in particular. The similarity is only that these tools also make use of SSH to run commands.

   ``ParallelSSH`` is in other words well suited to be the SSH client tools like Fabric and Ansible and others use to run their commands rather than a direct replacement for.

   By focusing on providing a well defined, lightweight - actual code is a few hundred lines - library, ``ParallelSSH`` is far better suited for *run this command on X number of hosts* tasks for which frameworks like Fabric, Capistrano and others are overkill and unsuprisignly, as it is not what they are for, ill-suited to and do not perform particularly well with.

   Fabric and tools like it are high level deployment frameworks - as opposed to general purpose libraries - for building deployment tasks to perform on hosts matching a role with task chaining, a DSL like syntax and are primarily intended for command line use for which the framework is a good fit for - very far removed from an SSH client *library*.

   Fabric in particular is a port of `Capistrano <https://github.com/capistrano/capistrano>`_ from Ruby to Python. Its design goals are to provide a faithful port of Capistrano with its `tasks` and `roles` framework to python with interactive command line being the intended usage.

   Furthermore, Fabric's use as a library is non-standard and in `many <https://github.com/fabric/fabric/issues/521>`_ `cases <https://github.com/fabric/fabric/pull/674>`_ `just <https://github.com/fabric/fabric/pull/1215>`_ `plain <https://github.com/fabric/fabric/issues/762>`_ `broken <https://github.com/fabric/fabric/issues/1068>`_ and currently stands at over 7,000 lines of code most of which is lacking code testing.

   In addition, Fabric's parallel command implementation uses a combination of both threads and processes with extremely high CPU usage and system load while running with as little as hosts in the single digits.

:Q:
   Is Windows supported?

:A:
   The library installs and works on Windows though not formally supported as unit tests are currently Posix system based.
 
   Pip versions >= 8.0 are required for binary package installation of ``gevent`` on Windows, a dependency of ``ParallelSSH``. 
 
   Though ``ParallelSSH`` is pure python code and will run on any platform that has a working Python interpreter, its ``gevent`` dependency and certain dependencies of ``paramiko`` contain native code which either needs a binary package to be provided for the platform or to be built from source. Binary packages for ``gevent`` are provided for OSX, Linux and Windows platforms as of this time of writing.

:Q:
   Are SSH agents used?

:A:
   All available keys in a system configured SSH agent in addition to SSH keys in the user's home directory, `~/.ssh/id_dsa`, `~/.ssh/id_rsa` et al are automatically used by ParallelSSH. 
 
   Use of SSH agent can be disabled by creating a client as ``ParallelSSHClient(allow_agent=False)``. `See documentation <http://parallel-ssh.readthedocs.org/en/latest/>`_ for more information.

:Q:
   Can ParallelSSH forward my SSH agent?

:A:
   SSH agent forwarding, what ``ssh -A`` does on the command line, is supported and enabled by default. Creating an object as ``ParallelSSHClient(forward_ssh_agent=False)`` will disable this behaviour.

:Q:
   Is tunneling/proxying supported?

:A:
   Yes, `ParallelSSH` natively supports tunelling - also known as proxying - through an intermediate SSH server. Connecting to a remote host is accomplished via an SSH tunnel using the SSH's protocol direct TCP tunneling feature, using local port forwarding. This is done natively in python and tunnel connections are asynchronous like all other connections in the `ParallelSSH` library. For example, client -> proxy SSH server -> remote SSH destination.

   Use the ``proxy_host`` and ``proxy_port`` parameters to configure your proxy::

     client = ParallelSSHClient(hosts, proxy_host='my_ssh_proxy_host')

   Note that while connections from the ParallelSSH `client` to the tunnel host are asynchronous, connections from the tunnel host to the remote destination(s) may not be, depending on the SSH server implementation. If the SSH server uses threading to implement its tunelling and that server is used to tunnel to a large number of remote destinations system load on the tunnel server will increase linearly with number of threads used.

:Q:
   Is there a way to programmatically provide an SSH key?

:A:
   Yes, use the ``pkey`` parameter of the `ParallelSSHClient class`_. There is also a ``load_private_key`` helper function in ``pssh.utils`` that can be used to load any supported key type. See `ParallelSSHClient class`_ documentation for examples.

:Q:
   Is there a way to programmatically provide an SSH agent?

:A:
   Yes, with the ``SSHAgent`` class that can be provided via the ``agent`` class parameter of `ParallelSSHClient class`_. Supplying an agent object in this way overrides use of the system's SSH agent, if any. See `SSHAgent documentation <http://parallel-ssh.readthedocs.io/en/latest/agent.html>`_ for an example.

:Q:
   Is there a user's group for feedback and discussion about ParallelSSH?

:A:
   There is a public `ParallelSSH Google group <https://groups.google.com/forum/#!forum/parallelssh>`_ setup for this purpose - both posting and viewing are open to the public.

.. _`ParallelSSHClient class`: http://parallel-ssh.readthedocs.io/en/latest/pssh_client.html#module-pssh.pssh_client
