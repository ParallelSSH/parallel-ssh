***********
Quickstart
***********

First, make sure that ``parallel-ssh`` is `installed <installation.html>`_.

.. note::

   ``parallel-ssh`` uses gevent's monkey patching to enable asynchronous use of the Python standard library's network I/O.

   Make sure that ParallelSSH imports come **before** any other imports in your code. Otherwise, patching may not be done before the standard library is loaded which will then cause ParallelSSH to block.

   If you are seeing messages like ``This operation would block forever``, this is the cause.

   Monkey patching is only done for the clients under ``pssh.pssh_client`` and ``pssh.ssh_client`` for parallel and single host clients respectively.

   New native library based clients under ``pssh.pssh2_client`` and ``pssh.ssh2_client`` **do not perform monkey patching** and are an option if monkey patching is not suitable. These clients will become the default in a future major release - ``2.0.0``.

Run a command on hosts in parallel
------------------------------------

The most basic usage of ``parallel-ssh`` is, unsurprisingly, to run a command on multiple hosts in parallel.

Examples in this documentation will be using ``print`` as a function, for which a future import is needed in Python ``2.7`` and below.

Make a list or other iterable of the hosts to run on:

.. code-block:: python

    from __future__ import print_function
    from pssh.pssh_client import ParallelSSHClient
    
    hosts = ['host1', 'host2', 'host3', 'host4']

Where ``host1`` to ``host4`` are valid host names. IP addresses may also be used.

Create a client for these hosts:

.. code-block:: python

    client = ParallelSSHClient(hosts)

The client object can, and should, be reused. Existing connections to hosts will remain alive as long as the client object is kept alive. Subsequent commands to the same host(s) will reuse their existing connection and benefit from much faster response times.

Now one or more commands can be run via the client:

.. code-block:: python

    output = client.run_command('whoami')

Once the call to ``run_command`` returns, the command has started executing in parallel.

Output is keyed by host and contains a `host output <output.html>`_ object. From that, SSH output is available.

Standard Output
----------------

Standard output, aka ``stdout`` for ``host1``:

.. code-block:: python

  for line in output['host1'].stdout:
      print(line)

:Output:
   .. code-block:: python

      <your username here>

There is nothing special needed to ensure output is available.

Please note that retrieving all of a command's standard output by definition requires that the command has completed.

Iterating over ``stdout`` for any host *to completion* will therefor *only complete* when that host's command has completed unless interrupted.

``stdout`` is a generator. Iterating over it will consume the remote standard output stream via the network as it becomes available. To retrieve all of stdout can wrap it with list, per below.

.. code-block:: python

   stdout = list(output['host1'].stdout)

.. warning::

   This will store the entirety of stdout into memory and may exhaust available memory if command output is large enough.

All hosts iteration
^^^^^^^^^^^^^^^^^^^^^

Of course, iterating over all hosts can also be done the same way.

.. code-block:: python

  for host, host_output in output.items():
      for line in host_output.stdout:
          print("Host [%s] - %s" % (host, line))

Exit codes
-------------

Exit codes are available on the host output object.

First, ensure that all commands have finished and exit codes gathered by joining on the output object, then iterate over all host's output to print their exit codes.

.. code-block:: python

  client.join(output)
  for host, host_output in output.items():
      print("Host %s exit code: %s" % (host, host_output.exit_code))

.. seealso:: 

   :py:class:`pssh.output.HostOutput`
       Host output class documentation.

Authentication
----------------

By default ``parallel-ssh`` will use an available SSH agent's credentials to login to hosts via private key authentication.

User/Password authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

User/password authentication can be used by providing user name and password credentials:

.. code-block:: python

  client = ParallelSSHClient(hosts, user='my_user', password='my_pass')

Programmatic Private Key authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is also possible to programmatically use a private key for authentication.

Native Client
______________

For the native client (``pssh.pssh2_client``), only private key filepath is needed. The corresponding public key *must* be available in the same directory as ``my_pkey.pub`` where private key file is ``my_pkey``. Public key file name and path will be made configurable in a future version.

 .. code-block:: python

   from pssh.pssh2_client import ParallelSSHClient

   client = ParallelSSHClient(hosts, pkey='my_pkey')

Paramiko Client
__________________

For the paramiko based client, the helper function :py:func:`load_private_key <pssh.utils.load_private_key>` is provided to easily load all possible key types. It takes either a file path or a file-like object.

 :File path:
   .. code-block:: python

      from pssh.pssh_client import ParallelSSHClient
      from pssh.utils import load_private_key
      
      pkey = load_private_key('my_pkey.pem')
      client = ParallelSSHClient(hosts, pkey=pkey)

.. note::

   The two available clients support different key types and authentication mechanisms - see Paramiko and libssh2 documentation for details, as well as `clients features comparison <ssh2.html>`_.

Output for Last Executed Commands
-----------------------------------

Output for last executed commands can be retrieved by ``get_last_output``:

.. code-block:: python

   client.run_command('uname')
   output = client.get_last_output()
   for host, host_output in output.items():
       for line in host.stdout:
           print(line)

This function can also be used to retrieve output for previously executed commands in the case where output object was not stored or is no longer available.

*New in 1.2.0*

Retrieving Last Executed Commands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Commands last executed by ``run_command`` can also be retrieved from the ``cmds`` attribute of ``ParallelSSHClient``:

.. code-block:: python

   client.run_command('uname')
   output = {}
   for i, host in enumerate(hosts):
       cmd = self.cmds[i]
       client.get_output(cmd, output)
       print("Got output for host %s from cmd %s" % (host, cmd))

*New in 1.2.0*

Host Logger
------------

There is a built in host logger that can be enabled to automatically log output from remote hosts. This requires the ``consume_output`` flag to be enabled on :py:func:`join <pssh.pssh_client.ParallelSSHClient.join>`.

The helper function ``pssh.utils.enable_host_logger`` will enable host logging to standard output, for example:

.. code-block:: python

  from pssh.utils import enable_host_logger
  enable_host_logger()

  output = client.run_command('uname')
  client.join(output, consume_output=True)

:Output:
   .. code-block:: python

      [localhost]	Linux

Using standard input
----------------------

Along with standard output and error, input is also available on the host output object. It can be used to send input to the remote host where required, for example password prompts or any other prompt requiring user input.

The ``stdin`` attribute is a file-like object giving access to the remote stdin channel that can be written to:

.. code-block:: python

  output = client.run_command('read')
  stdin = output['localhost'].stdin
  stdin.write("writing to stdin\\n")
  stdin.flush()
  for line in output['localhost'].stdout:
      print(line)

:Output:
   .. code-block:: python

      writing to stdin

Errors and Exceptions
-----------------------

By default, ``parallel-ssh`` will fail early on any errors connecting to hosts, whether that be connection errors such as DNS resolution failure or unreachable host, SSH authentication failures or any other errors.

Alternatively, the ``stop_on_errors`` flag is provided to tell the client to go ahead and attempt the command(s) anyway and return output for all hosts, including the exception on any hosts that failed:

.. code-block:: python

  output = client.run_command('whoami', stop_on_errors=False)

With this flag, the ``exception`` attribute will contain the exception on any failed hosts, or ``None``:

.. code-block:: python

  client.join(output)
  for host, host_output in output.items():
      print("Host %s: exit code %s, exception %s" % (
            host, host_output.exit_code, host_output.exception))

:Output:
   .. code-block:: python

      host1: 0, None
      host2: None, AuthenticationException <..>

.. seealso::

   Exceptions raised by the library can be found in :mod:`pssh.exceptions` module.
