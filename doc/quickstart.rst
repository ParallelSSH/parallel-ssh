***********
Quickstart
***********

First, make sure that `parallel-ssh` is `installed <installation>`_.

Run a command on hosts in parallel
------------------------------------

The most basic usage of `parallel-ssh` is, unsurprisingly, to run a command on multiple hosts in parallel.

Examples here will be using `print` as a function, for which a future import is needed for Python `2.7`.

Make a list of the hosts to run on::

    from __future__ import print_function

    hosts = ['host1', 'host2', 'host3', 'host4']

Where `host1` to `host4` are valid host names. IP addresses may also be used.

Create a client for these hosts::

    client = ParallelSSHClient(hosts)

The client object can, and should, be reused. Existing connections to hosts will remain alive as long as the client object is kept alive. Subsequent commands to the same host(s) will reuse their existing connection and benefit from much faster response times.

Now one or more commands can be run via the client::

    output = client.run_command('whoami')

At this point the remote command has started executing in parallel.

Output is keyed by host and contains a host output object. From that, SSH output is available

Authentication
----------------

By default `parallel-ssh` will use an available SSH agent's credentials to login to hosts via private key authentication.

User/Password authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

User/password authentication can be used by providing user name and password credentials::

  client = ParallelSSHClient(hosts, user='my_user', password='my_pass')

Programmatic Private Key authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is also possible to programmatically use a private key for authentication. 

The helper function `pssh.utils.load_private_key` is provided to easily load all possible key types. It takes either a file path or a file-like object.

File path::

  from pssh.utils import load_private_key
  pkey = load_private_key('my_pkey.pem')
  client = ParallelSSHClient(hosts, pkey=pkey)

File object::

  from pssh.utils import load_private_key
  pkey = load_private_key(open('my_pkey.pem'))
  client = ParallelSSHClient(hosts, pkey=pkey)  


Standard Output
----------------

Standard output, aka `stdout` for `host1`::

  for line in output['host1']:
      print(line)

Output::

  <your username here>

There is nothing special needed to ensure output is available.

Please note that retrieving all of a command's standard output by definition requires that the command has completed.

Iterating over the `stdout` attribute for any host will therefor *block* until that host's command has completed unless interrupted.


All hosts iteration
^^^^^^^^^^^^^^^^^^^^^

Of course, iterating over all hosts can also be done the same way::

  for host, host_output in output.items():
      for line in host_output:
          print("Host %s: %s" % (host, line))

Exit codes
-------------

Exit codes are available on the host output object.

First, ensure that all commands have finished and exit codes gathered by joining on the output object, then iterate over all hosts::

  client.join(output)
  for host, host_output in output.items():
      print("Host %s exit code: %s" % (host, host_output.exit_code))

Host Logger
------------

There is a built in host logger that can be enabled to log output from remote hosts. The helper function ``pssh.utils.enable_host_logger`` will enable host logging to standard output, for example ::

  from pssh.utils import enable_host_logger
  enable_host_logger()
  client.join(client.run_command('uname'))
  
  [localhost]	Linux

Using standard input
----------------------

Along with standard output and error, input is also available on the host output object. It can be used to send input to the remote host where required, for example password prompts or any other prompt requiring user input.

The `stdin` channel is a file-like object that can be written to::

  output = client.run_command('read')
  stdin = output['localhost'].stdin
  stdin.write("writing to stdin\\n")
  stdin.flush()
  for line in output['localhost'].stdout:
      print(line)

Output::

  writing to stdin

Errors and Exceptions
-----------------------

By default, `parallel-ssh` will fail early on any errors connecting to hosts, whether that be connection errors such as DNS resolution failure or unreachable host, SSH authentication failures or any other errors.

Alternatively, the `stop_on_errors` flag is provided to tell the client to go ahead and attempt the command(s) anyway and return output for all hosts, including the exception on any hosts that failed::

  output = client.run_command('whoami', stop_on_errors=False)

With this flag, the `exception` attribute will contain the exception on any failed hosts, or `None`::

  client.join(output)
  for host, host_output in output.items():
      print("Host %s: exit code %s, exception %s" % (
            host, host_output.exit_code, host_output.exception))

Output::

  host1: 0, None
  host2: None, AuthenticationException <..>

Possible exceptions can be found in :mod:`pssh.exceptions` module.
