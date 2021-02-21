============
parallel-ssh
============

Asynchronous parallel SSH client library.

Run SSH commands over many - hundreds/hundreds of thousands - number of servers asynchronously and with minimal system load on the client host.

Native code based clients with extremely high performance, making use of C libraries.

.. image:: https://img.shields.io/badge/License-LGPL%20v2.1-blue.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: License
.. image:: https://img.shields.io/pypi/v/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: Latest Version
.. image:: https://circleci.com/gh/ParallelSSH/parallel-ssh/tree/master.svg?style=svg
  :target: https://circleci.com/gh/ParallelSSH/parallel-ssh
.. image:: https://codecov.io/gh/ParallelSSH/parallel-ssh/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/ParallelSSH/parallel-ssh
.. image:: https://img.shields.io/pypi/wheel/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: https://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation

.. _`read the docs`: https://parallel-ssh.readthedocs.org/en/latest/

************
Installation
************

.. code-block:: shell

   pip install parallel-ssh


An update to `pip` may be needed to be able to install binary wheels.

.. code-block:: shell

   pip install -U pip
   pip install parallel-ssh


*************
Usage Example
*************

See documentation on `read the docs`_ for more complete examples.

Run ``uname`` on two hosts in parallel.

.. code-block:: python

  from pssh.clients import ParallelSSHClient

  hosts = ['localhost', 'localhost']
  client = ParallelSSHClient(hosts)

  output = client.run_command('uname')
  for host_output in output:
      for line in host_output.stdout:
          print(line)
      exit_code = host_output.exit_code

:Output:

   .. code-block:: shell

      Linux
      Linux


Single Host Client
*******************

Single host client with similar API can be used if parallel functionality is not needed.

.. code-block:: python

   from pssh.clients import SSHClient

   host = 'localhost'
   cmd = 'uname'
   client = SSHClient(host)

   host_out = client.run_command(cmd)
   for line in host_out.stdout:
       print(line)
   exit_code = host_out.exit_code


.. contents::


************************
Questions And Discussion
************************

`Github discussions <https://github.com/ParallelSSH/parallel-ssh/discussions>`_ can be used to discuss, ask questions and share ideas regarding the use of parallel-ssh.


**************
Native clients
**************

The default client in ``parallel-ssh`` is a native client based on ``ssh2-python`` - ``libssh2`` C library - which offers much greater performance and reduced overhead compared to other Python SSH libraries.

See `this post <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_ for a performance comparison of different Python SSH libraries.

Alternative clients based on ``ssh-python`` (``libssh``) are also available under ``pssh.clients.ssh``. See `client documentation <https://parallel-ssh.readthedocs.io/en/latest/clients.html>`_ for a feature comparison of the available clients in the library.

``parallel-ssh`` makes use of clients and an event loop solely based on C libraries providing native code levels of performance and stability with an easy to use Python API.


Native Code Client Features
****************************

* Highest performance and least overhead of any Python SSH library
* Thread safe - makes use of native threads for CPU bound calls like authentication
* Natively asynchronous utilising C libraries implementing the SSH protocol
* Significantly reduced overhead in CPU and memory usage


****************
Why This Library
****************

Because other options are either immature, unstable, lacking in performance or all of the aforementioned.

Certain other self-proclaimed *leading* Python SSH libraries leave a lot to be desired from a performance and stability point of view, as well as suffering from a lack of maintenance with hundreds of open issues, unresolved pull requests and inherent design flaws.

The SSH libraries ``parallel-ssh`` uses are, on the other hand, long standing mature C libraries in `libssh2 <https://libssh2.org>`_ and `libssh <https://libssh.org>`_ that have been in production use for decades and are part of some of the most widely distributed software available today - `Git` itself, `OpenSSH`, `Curl` and many others.

These low level libraries are far better placed to provide the maturity, stability and performance needed from an SSH client for production use.

``parallel-ssh`` provides easy to use SSH clients that hide the complexity, while offering stability and native code levels of performance and as well as the ability to scale to hundreds or more concurrent hosts.

See `alternatives <https://parallel-ssh.readthedocs.io/en/latest/alternatives.html>`_ for a more complete comparison of alternative SSH libraries, as well as `performance comparisons <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_ mentioned previously.


*************************************
Waiting for Completion and Exit Codes
*************************************

The client's ``join`` function can be used to wait for all commands in output to finish.

After ``join`` returns, commands have finished and all output can be read without blocking.

Once *either* standard output is iterated on *to completion*, or ``client.join()`` is called, exit codes become available in host output.

Iteration ends *only when remote command has completed*, though it may be interrupted and resumed at any point - see `join and output timeouts <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#join-and-output-timeouts>`_ documentation.

``HostOutput.exit_code`` is a dynamic property and will return ``None`` when exit code is not ready, meaning command has not finished, or unavailable due to error.

Once all output has been gathered exit codes become available even without calling ``join`` as per previous examples.

.. code-block:: python

  output = client.run_command('uname')

  client.join()

  for host_out in output:
      for line in host_out.stdout:
          print(line)
      print(host_out.exit_code)

:Output:
   .. code-block:: python

      Linux
      0
      Linux
      0


Similarly, exit codes are available after ``client.join()`` without reading output.


.. code-block:: python

  output = client.run_command('uname')

  client.join()

  for host_output in output:
      print(host_out.exit_code)

:Output:
   .. code-block:: python

      0
      0


***************************
Built in Host Output Logger
***************************

There is also a built in host logger that can be enabled to log output from remote hosts for both stdout and stderr. The helper function ``pssh.utils.enable_host_logger`` will enable host logging to stdout.

To log output without having to iterate over output generators, the ``consume_output`` flag *must* be enabled - for example:

.. code-block:: python

  from pssh.utils import enable_host_logger

  enable_host_logger()
  client.run_command('uname')
  client.join(consume_output=True)

:Output:
   .. code-block:: shell

      [localhost]	Linux


****
SCP
****

SCP is supported - native client only - and provides the best performance for file copying.

Unlike with the SFTP functionality, remote files that already exist are *not* overwritten and an exception is raised instead.

Note that enabling recursion with SCP requires server SFTP support for creating remote directories.

To copy a local file to remote hosts in parallel with SCP:

.. code-block:: python

  from pssh.clients import ParallelSSHClient
  from gevent import joinall

  hosts = ['myhost1', 'myhost2']
  client = ParallelSSHClient(hosts)
  cmds = client.scp_send('../test', 'test_dir/test')
  joinall(cmds, raise_error=True)

See `SFTP and SCP documentation <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#sftp-scp>`_ for more examples.


*****
SFTP
*****

SFTP is supported in the native client.

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

There is similar capability to copy remote files to local ones with configurable file names via the `copy_remote_file <https://parallel-ssh.readthedocs.io/en/latest/base_parallel.html#pssh.clients.base.parallel.BaseParallelSSHClient.copy_remote_file>`_ function.

In addition, per-host configurable file name functionality is provided for both SFTP and SCP  - see `documentation <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#copy-args>`_.

Directory recursion is supported in both cases via the ``recurse`` parameter - defaults to off.

See `SFTP and SCP documentation <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#sftp-scp>`_ for more examples.


.. image:: https://ga-beacon.appspot.com/UA-9132694-7/parallel-ssh/README.rst?pixel
  :target: https://github.com/igrigorik/ga-beacon
