============
parallel-ssh
============

Non-blocking, asynchronous parallel SSH client library.

Run SSH commands over many - hundreds/hundreds of thousands - number of servers asynchronously and with minimal system load on the client host.

Native code based client with extremely high performance - based on ``libssh2`` C library.

.. image:: https://img.shields.io/badge/License-LGPL%20v2-blue.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: License
.. image:: https://img.shields.io/pypi/v/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: Latest Version
.. image:: https://travis-ci.org/ParallelSSH/parallel-ssh.svg?branch=master
  :target: https://travis-ci.org/ParallelSSH/parallel-ssh
.. image:: https://ci.appveyor.com/api/projects/status/github/parallelssh/parallel-ssh?svg=true&branch=master
  :target: https://ci.appveyor.com/project/pkittenis/parallel-ssh-4nme1
.. image:: https://codecov.io/gh/ParallelSSH/parallel-ssh/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/ParallelSSH/parallel-ssh
.. image:: https://img.shields.io/pypi/wheel/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: http://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation

.. _`read the docs`: http://parallel-ssh.readthedocs.org/en/latest/

.. contents::

************
Installation
************

.. code-block:: shell

   pip install parallel-ssh

*************
Usage Example
*************

See documentation on `read the docs`_ for more complete examples.

Run ``uname`` on two remote hosts in parallel with ``sudo``.

.. code-block:: python

  from __future__ import print_function

  from pssh.pssh_client import ParallelSSHClient

  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)

  output = client.run_command('uname')
  for host, host_output in output.items():
      for line in host_output.stdout:
          print(line)

:Output:

   .. code-block:: shell

      Linux
      Linux

**************
Native client
**************

Starting from version ``1.2.0``, a new client is supported in ``parallel-ssh`` which offers much greater performance and reduced overhead than the current default client.

The new client is based on ``libssh2`` via the ``ssh2-python`` extension library and supports non-blocking mode natively. Binary wheel packages with ``libssh2`` included are provided for Linux, OSX and Windows platforms and all supported Python versions.

See `this post <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_ for a performance comparison of the available clients.

To make use of this new client, ``ParallelSSHClient`` can be imported from ``pssh.clients.native`` instead. Their respective APIs are almost identical.

The new client will become the default and will replace the current ``pssh.pssh_client`` in a new major version of the library - ``2.0.0``.

The paramiko based client will become an optional install via pip `extras`, available under ``pssh.clients.miko``.

For example:

.. code-block:: python

  from pprint import pprint
  from pssh.clients.native import ParallelSSHClient

  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)

  output = client.run_command('uname')
  for host, host_output in output.items():
      for line in host_output.stdout:
          print(line)


See `documentation <http://parallel-ssh.readthedocs.io/en/latest/ssh2.html>`_ for a feature comparison of the two clients.


****************************
Native Code Client Features
****************************

* Highest performance and least overhead of any Python SSH libraries
* Thread safe - makes use of native threads for blocking calls like authentication
* Natively non-blocking utilising ``libssh2`` via ``ssh2-python`` - **no monkey patching of the Python standard library**
* Significantly reduced overhead in CPU and memory usage


***********
Exit codes
***********

Once either standard output is iterated on *to completion*, or ``client.join(output)`` is called, exit codes become available in host output. Iteration ends *only when remote command has completed*, though it may be interrupted and resumed at any point.

.. code-block:: python

  for host in output:
      print(output[host].exit_code)

:Output:
   .. code-block:: python

      0
      0


The client's ``join`` function can be used to wait for all commands in output object to finish:

.. code-block:: python

  client.join(output)

Similarly, output and exit codes are available after ``client.join`` is called:

.. code-block:: python

  from pprint import pprint

  output = client.run_command('exit 0')

  # Wait for commands to complete and gather exit codes. 
  # Output is updated in-place.
  client.join(output)
  pprint(output.values()[0].exit_code)

  # Output remains available in output generators
  for host, host_output in output.items():
      for line in host_output.stdout:
          pprint(line)

:Output:
   .. code-block:: python

      0
      <..stdout..>


There is also a built in host logger that can be enabled to log output from remote hosts. The helper function ``pssh.utils.enable_host_logger`` will enable host logging to stdout.

To log output without having to iterate over output generators, the ``consume_output`` flag *must* be enabled - for example:

.. code-block:: python

  from pssh.utils import enable_host_logger

  enable_host_logger()
  client.join(client.run_command('uname'), consume_output=True)

:Output:
   .. code-block:: shell

      [localhost]	Linux


SFTP
******

SFTP is supported natively.

To copy a local file to remote hosts in parallel:

.. code-block:: python

  from pssh.clients import ParallelSSHClient
  from pssh.utils import enable_logger, logger
  from gevent import joinall

  enable_logger(logger)
  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)
  cmds = client.copy_file('../test', 'test_dir/test')
  joinall(cmds, raise_error=True)

:Output:
   .. code-block:: python

      Copied local file ../test to remote destination myhost1:test_dir/test
      Copied local file ../test to remote destination myhost2:test_dir/test

There is similar capability to copy remote files to local ones suffixed with the host's name with the ``copy_remote_file`` function.

Directory recursion is supported in both cases via the ``recurse`` parameter - defaults to off.

See `SFTP documentation <http://parallel-ssh.readthedocs.io/en/latest/advanced.html#sftp>`_ for more examples.


*****************
Design And Goals
*****************

``parallel-ssh``'s design goals and motivation are to provide a *library* for running *non-blocking* asynchronous SSH commands in parallel with little to no load induced on the system by doing so with the intended usage being completely programmatic and non-interactive.

To meet these goals, API driven solutions are preferred first and foremost. This frees up developers to drive the library via any method desired, be that environment variables, CI driven tasks, command line tools, existing OpenSSH or new configuration files, from within an application et al.


Comparison With Alternatives
*****************************

There are not many alternatives for SSH libraries in Python. Of the few that do exist, here is how they compare with ``parallel-ssh``.

As always, it is best to use a tool that is suited to the task at hand. ``parallel-ssh`` is a library for programmatic and non-interactive use - see `Design And Goals`_. If requirements do not match what it provides then it best not be used. Same applies for the tools described below.

Paramiko
________

The default SSH client library in ``parallel-ssh`` ``1.x.x`` series.

Pure Python code, while having native extensions as dependencies, with poor performance and numerous bugs compared to both OpenSSH binaries and the ``libssh2`` based native clients in ``parallel-ssh`` ``1.2.x`` and above. Recent versions have regressed in performance and have `blocker issues <https://github.com/ParallelSSH/parallel-ssh/issues/83>`_.

It does not support non-blocking mode, so to make it non-blocking monkey patching must be used which affects all other uses of the Python standard library. However, some functionality like Kerberos (GSS-API) authentication is not provided by other libraries.

asyncssh
________

Python 3 only ``asyncio`` framework using client library. License (`EPL`) is not compatible with GPL, BSD or other open source licenses and `combined works cannot be distributed <https://www.eclipse.org/legal/eplfaq.php#USEINANOTHER>`_.

Therefore unsuitable for use in many projects, including ``parallel-ssh``.

Fabric
______

Port of Capistrano from Ruby to Python. Intended for command line use and is heavily systems administration oriented rather than non-interactive library. Same maintainer as Paramiko.

Uses Paramiko and suffers from the same limitations. More over, uses threads for parallelisation, while `not being thread safe <https://github.com/fabric/fabric/issues/1433>`_, and exhibits very poor performance and extremely high CPU usage even for limited number of hosts - 1 to 10 - with scaling limited to one core.

Library API is non-standard, poorly documented and with numerous issues as API use is not intended.

Ansible
_______

A configuration management and automation tool that makes use of SSH remote commands. Uses, in parts, both Paramiko and OpenSSH binaries.

Similarly to Fabric, uses threads for parallelisation and suffers from the poor scaling that this model offers.

See `The State of Python SSH Libraries <https://parallel-ssh.org/post/ssh2-python/>`_ for what to expect from scaling SSH with threads, as compared `to non-blocking I/O <https://parallel-ssh.org/post/parallel-ssh-libssh2/>`_ with ``parallel-ssh``.

Again similar to Fabric, its intended and documented use is interactive via command line rather than library API based. It may, however, be an option if Ansible is already being used for automation purposes with existing playbooks, the number of hosts is small, and when the use case is interactive via command line.

``parallel-ssh`` is, on the other hand, a suitable option for Ansible as an SSH client that would improve its parallel SSH performance significantly.

ssh2-python
___________

Wrapper to ``libssh2`` C library. Used by ``parallel-ssh`` as of ``1.2.0`` and is by same author.

Does not do parallelisation out of the box but can be made parallel via Python's ``threading`` library relatively easily and as it is a wrapper to a native library that releases Python's GIL, can scale to multiple cores.

``parallel-ssh`` uses ``ssh2-python`` in its native non-blocking mode with event loop and co-operative sockets provided by ``gevent`` for an extremely high performance library without the side-effects of monkey patching - see `benchmarks <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_.

In addition, ``parallel-ssh`` uses native threads to offload CPU blocked tasks like authentication in order to scale to multiple cores while still remaining non-blocking for network I/O.

``pssh.ssh2_client.SSHClient`` is a single host natively non-blocking client for users that do not need parallel capabilities but still want a non-blocking client with native code performance.

Out of all the available Python SSH libraries, ``libssh2`` and ``ssh2-python`` have been shown, see benchmarks above, to perform the best with the least resource utilisation and ironically for a native code extension the least amount of dependencies. Only ``libssh2`` C library and its dependencies which are included in binary wheels.

However, it lacks support for some SSH features present elsewhere like ECDSA keys (`PR pending <https://github.com/libssh2/libssh2/pull/206>`_), agent forwarding (`PR also pending <https://github.com/libssh2/libssh2/pull/219>`_) and Kerberos authentication - see `feature comparison <http://parallel-ssh.readthedocs.io/en/latest/ssh2.html>`_.


********
Scaling
********

Some guide lines on scaling ``parallel-ssh`` and pool size numbers.

In general, long lived commands with little or no output *gathering* will scale better. Pool sizes in the multiple thousands have been used successfully with little CPU overhead in the single thread running them in these use cases.

Conversely, many short lived commands with output gathering will not scale as well. In this use case, smaller pool sizes in the hundreds are likely to perform better with regards to CPU overhead in the event loop.

Multiple Python native threads, each of which can get its own event loop, may be used to scale this use case further as number of CPU cores allows. Note that ``parallel-ssh`` imports *must* be done within the target function of the newly started thread for it to receive its own event loop. ``gevent.get_hub()`` may be used to confirm that the worker thread event loop differs from the main thread.

Gathering is highlighted here as output generation does not affect scaling. Only when output is gathered either over multiple still running commands, or while more commands are being triggered, is overhead increased.

Technical Details
******************

To understand why this is, consider that in co-operative multi tasking, which is being used in this project via the ``gevent`` library, a co-routine (greenlet) needs to ``yield`` the event loop to allow others to execute - *co-operation*. When one co-routine is constantly grabbing the event loop in order to gather output, or when co-routines are constantly trying to start new short-lived commands, it causes contention with other co-routines that also want to use the event loop.

This manifests itself as increased CPU usage in the process running the event loop and reduced performance with regards to scaling improvements from increasing pool size.

On the other end of the spectrum, long lived remote commands that generate *no* output only need the event loop at the start, when they are establishing connections, and at the end, when they are finished and need to gather exit codes, which results in practically zero CPU overhead at any time other than start or end of command execution.

Output *generation* is done remotely and has no effect on the event loop until output is gathered - output buffers are iterated on. Only at that point does the event loop need to be held.

*************
User's group
*************

There is a public `ParallelSSH Google group <https://groups.google.com/forum/#!forum/parallelssh>`_ setup for this purpose - both posting and viewing are open to the public.

.. image:: https://ga-beacon.appspot.com/UA-9132694-7/parallel-ssh/README.rst?pixel
  :target: https://github.com/igrigorik/ga-beacon
