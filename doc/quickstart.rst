***********
Quickstart
***********

First, make sure that ``parallel-ssh`` is `installed <installation.html>`_.

Run a command on hosts in parallel
====================================

The most basic usage of ``parallel-ssh`` is, unsurprisingly, to run a command on multiple hosts in parallel.

A complete example is shown below.

Examples all assume a valid key is available on a running SSH agent. See `Programmatic Private Key Authentication <quickstart.html#pkey-auth>`_ for authenticating without an SSH agent.


Complete Example
-----------------

Host list can contain identical hosts. Commands are executed concurrently on every host given to the client regardless.

.. code-block:: python

   from pssh.clients import ParallelSSHClient

   hosts = ['localhost', 'localhost', 'localhost', 'localhost']
   client = ParallelSSHClient(hosts)
   cmd = 'uname'

   output = client.run_command(cmd)
   for host_out in output:
       for line in host_out.stdout:
           print(line)


Output:
  .. code-block:: bash

     Linux
     Linux
     Linux
     Linux


Single Host Client
====================

``parallel-ssh`` has a fully featured, non-blocking single host client that it uses for all its parallel commands.

Users that do not need the parallel capabilities can use the single host client for a simpler way to run asynchronous non-blocking commands on a remote host.

.. code-block:: python

   from pssh.clients import SSHClient

   host = 'localhost'
   cmd = 'uname'
   client = SSHClient(host)

   host_out = client.run_command(cmd)
   for line in host_out.stdout:
       print(line)

Output::
  .. code-block:: bash

     Linux


Step by Step
-------------

Make a list or other iterable of the hosts to run on:

.. code-block:: python

    from pssh.clients import ParallelSSHClient
    
    hosts = ['host1', 'host2', 'host3', 'host4']

Where ``host1`` to ``host4`` are valid host names. IP addresses may also be used.

Create a client for these hosts:

.. code-block:: python

    client = ParallelSSHClient(hosts)

The client object can, and should, be reused. Existing connections to hosts will remain alive as long as the client object is kept alive. Subsequent commands to the same host(s) will reuse their existing connection and benefit from much faster response times.

Now one or more commands can be run via the client:

.. code-block:: python

    output = client.run_command('uname')

When the call to ``run_command`` returns, the remote commands are already executing in parallel.


Run Command Output
===================

Standard Output
----------------

Standard output, aka ``stdout``, for a given :py:class:`HostOutput <pssh.output.HostOutput>` object.

.. code-block:: python

  for line in host_out.stdout:
      print(line)

:Output:
   .. code-block:: python

      <line by line output>
      <line by line output>
      <..>

There is nothing special needed to ensure output is available.

Please note that retrieving all of a command's standard output by definition requires that the command has completed.

Iterating over ``stdout`` for any host *to completion* will therefor *only complete* when that host's command has completed unless interrupted.

The ``timeout`` keyword argument to ``run_command`` may be used to cause output generators to timeout if no output is received after the given number of seconds - see `join and output timeouts <advanced.html#join-and-output-timeouts>`_.

``stdout`` is a generator. Iterating over it will consume the remote standard output stream via the network as it becomes available. To retrieve all of stdout can wrap it with list, per below.

.. code-block:: python

   stdout = list(host_out.stdout)

.. warning::

   This will store the entirety of stdout into memory.

All hosts iteration
-------------------

Of course, iterating over all hosts can also be done the same way.

.. code-block:: python

  for host_output in output:
      for line in host_output.stdout:
          print("Host [%s] - %s" % (host, line))

.. _host-list-output:

Complete Example
----------------

.. code-block:: python

  from pssh.clients import ParallelSSHClient

  client = ParallelSSHClient(['localhost', 'localhost'])
  output = client.run_command('whoami')
  client.join(output)

  for host_output in output:
      hostname = host_output.host
      stdout = list(host_output.stdout)
      print("Host %s: exit code %s, output %s" % (
            hostname, host_output.exit_code, stdout))

:Output:
   .. code-block:: python

       localhost: exit code 0, stdout ['<username>']
       localhost: exit code 0, stdout ['<username>']

*New in 1.10.0*

Exit codes
==============

Exit codes are available on the host output object as a dynamic property. Exit code will be ``None`` if not available, or the exit code as reported by channel.

First, ensure that all commands have finished by either joining on the output object or gathering all output, then iterate over all host's output to print their exit codes.

.. code-block:: python

  client.join(output)
  for host, host_output in output:
      print("Host %s exit code: %s" % (host, host_output.exit_code))

As of ``1.11.0``, ``client.join`` is not required as long as output has been gathered.

.. code-block:: python

  for host_out in output:
      for line in host_out.stdout:
          print(line)
      print(host_out.exit_code)


.. seealso:: 

   :py:class:`pssh.output.HostOutput`
       Host output class documentation.

Authentication
=================

By default ``parallel-ssh`` will use an available SSH agent's credentials to login to hosts via public key authentication.

User/Password authentication
-------------------------------

User/password authentication can be used by providing user name and password credentials:

.. code-block:: python

  client = ParallelSSHClient(hosts, user='my_user', password='my_pass')

.. note::

   On Posix platforms, user name defaults to the current user if not provided.

   On Windows, user name is required.


.. _pkey-auth:

Programmatic Private Key authentication
------------------------------------------

It is also possible to programmatically provide a private key for authentication.

.. code-block:: python

   from pssh.clients import ParallelSSHClient

   client = ParallelSSHClient(hosts, pkey='my_pkey')


Where ``my_pkey`` is a private key file in the current directory.

To use files under a user's ``.ssh`` directory:

.. code-block:: python

   import os

   client = ParallelSSHClient(hosts, pkey='~/.ssh/my_pkey')


Output for Last Executed Commands
==================================

Output for last executed commands can be retrieved by ``get_last_output``:

.. code-block:: python

   client.run_command('uname')
   output = client.get_last_output()
   for host_output in output:
       for line in host_output.stdout:
           print(line)

This function can also be used to retrieve output for previously executed commands in the case where output object was not stored or is no longer available.

*New in 1.2.0*

.. _host logger:

Host Logger
=============

There is a built in host logger that can be enabled to automatically log standard output from remote hosts. This requires the ``consume_output=True`` flag on :py:func:`join <pssh.clients.native.parallel.ParallelSSHClient.join>`.

The helper function :py:func:`pssh.utils.enable_host_logger` will enable host logging to standard output, for example:

.. code-block:: python

  from pssh.utils import enable_host_logger
  enable_host_logger()

  output = client.run_command('uname')
  client.join(output, consume_output=True)

:Output:
   .. code-block:: python

      [localhost]	Linux

Using standard input
======================

Along with standard output and error, input is also available on the host output object. It can be used to send input to the remote host where required, for example password prompts or any other prompt requiring user input.

The ``stdin`` attribute on :py:class:`HostOutput <pssh.output.HostOutput>` is a file-like object giving access to the remote stdin channel that can be written to:

.. code-block:: python

  output = client.run_command('read')
  host_output = output[0]
  stdin = host_output.stdin
  stdin.write("writing to stdin\\n")
  stdin.flush()
  for line in host_output.stdout:
      print(line)

:Output:
   .. code-block:: python

      writing to stdin

Errors and Exceptions
========================

By default, ``parallel-ssh`` will raise exception on any errors connecting to hosts, whether that be connection errors such as DNS resolution failure or unreachable host, SSH authentication failures or any other errors.

Alternatively, the ``stop_on_errors`` flag is provided to tell the client to go ahead and attempt the command(s) anyway and return output for all hosts, including the exception on any hosts that failed:

.. code-block:: python

  output = client.run_command('whoami', stop_on_errors=False)

With this flag, the ``exception`` output attribute will contain the exception on any failed hosts, or ``None``:

.. code-block:: python

  client.join(output)
  for host_output in output:
      host = host_output.host
      print("Host %s: exit code %s, exception %s" % (
            host, host_output.exit_code, host_output.exception))

:Output:
   .. code-block:: python

      host1: 0, None
      host2: None, AuthenticationException <..>

.. seealso::

   Exceptions raised by the library can be found in the :mod:`pssh.exceptions` module and in API documentation.
