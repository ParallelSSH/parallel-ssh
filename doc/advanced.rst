Advanced Usage
###############

There are several more advanced usage features of ``parallel-ssh``, such as tunnelling (aka proxying) via an intermediate SSH server and per-host configuration and command substitution among others.

Agents and Private Keys
************************

Programmatic Private Keys
============================

By default, ``parallel-ssh`` will attempt to use loaded keys in an available SSH agent as well as default identity files under the user's home directory.

See `IDENTITIES` in :py:class:`SSHClient <pssh.clients.base.single.BaseSSHClient.IDENTITIES>` for the list of default identity files.

A private key can also be provided programmatically.

.. code-block:: python

   from pssh.clients import ParallelSSHClient

   client = ParallelSSHClient(hosts, pkey="~/.ssh/my_key")

Where ``my_key`` is a private key file under `.ssh` in the user's home directory.


In-Memory Private Keys
========================

Private key data can also be provided as bytes for authentication from in-memory private keys.

.. code-block:: python

   from pssh.clients import ParallelSSHClient

   pkey_data = b"""-----BEGIN RSA PRIVATE KEY-----
   <key data>
   -----END RSA PRIVATE KEY-----
   """
   client = ParallelSSHClient(hosts, pkey=pkey_data)

Private key data provided this way *must* be in bytes. This is supported by all parallel and single host clients.


Native Clients
***************

ssh2-python (libssh2)
=====================

The default client in ``parallel-ssh`` is based on `ssh2-python` (`libssh2`). It is a native client, offering C level performance with an easy to use Python API.

See `this post <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_ for a performance comparison of the available clients in the `1.x.x` series.


.. code-block:: python

   from pssh.clients import ParallelSSHClient, SSHClient

   hosts = ['my_host', 'my_other_host']
   client = ParallelSSHClient(hosts)

   output = client.run_command('uname')
   for host_out in output:
       for line in host_out.stdout:
           print(line)


.. seealso::

   `Feature comparison <clients.html>`_ for how the `2.x.x` client types compare.

   API documentation for `parallel <native_parallel.html>`_ and `single <native_single.html>`_ native clients.


*New in 1.2.0*

ssh-python (libssh) Client
============================

A set of alternative clients based on `libssh <https://libssh.org>`_ via `ssh-python <https://github.com/ParallelSSH/ssh-python>`_ are also provided.

The API is similar to the default client, while ``ssh-python`` offers more supported authentication methods compared to the default client, such as certificate and GSS API authentication.

On the other hand, these clients lack SCP, SFTP and proxy functionality.

.. code-block:: python

   from pssh.clients.ssh import ParallelSSHClient, SSHClient

   hosts = ['localhost', 'localhost']
   client = ParallelSSHClient(hosts)

   output = client.run_command('uname')
   client.join(output)
   for host_out in output:
       for line in host_out.stdout:
           print(line)

.. seealso::

   API documentation for :py:class:`parallel <pssh.clients.ssh.parallel.ParallelSSHClient>` and :py:class:`single <pssh.clients.ssh.single.SSHClient>` ssh-python clients.


*New in 1.12.0*

GSS-API Authentication - aka Kerberos
--------------------------------------

GSS authentication allows logins using Windows LDAP configured user accounts via Kerberos on Linux.

.. code-block:: python

   from pssh.clients.ssh import ParallelSSHClient

   client = ParallelSSHClient(hosts, gssapi_auth=True, gssapi_server_identity='gss_server_id')

   output = client.run_command('id')
   client.join(output)
   for host_out in output:
       for line in output.stdout:
           print(line)


``ssh-python`` :py:class:`ParallelSSHClient <pssh.clients.ssh.parallel.ParallelSSHClient>` only.


Certificate authentication
--------------------------

In the ``pssh.clients.ssh`` clients, certificate authentication is supported.

.. code-block:: python

   from pssh.clients.ssh import ParallelSSHClient

   client = ParallelSSHClient(
       hosts, pkey='id_rsa', cert_file='id_rsa-cert.pub')


Where ``id_rsa-cert.pub`` is an RSA signed certificate file for the ``id_rsa`` private key.

Both private key and corresponding signed public certificate file must be provided.

``ssh-python`` :py:mod:`ParallelSSHClient <pssh.clients.ssh.parallel.ParallelSSHClient>` only.


Proxy Hosts and Tunneling
**************************

This is used in cases where the client does not have direct access to the target host(s) and has to authenticate via an intermediary proxy, also called a bastion host.

Commonly used for additional security as only the proxy host needs to have access to the target host.

Client       -------->        Proxy host         -------->         Target host

Proxy host can be configured as follows in the simplest case:

.. code-block:: python

  hosts = [<..>]
  client = ParallelSSHClient(hosts, proxy_host='bastion')

For single host clients:

.. code-block:: python

   host = '<..>'
   client = SSHClient(host, proxy_host='proxy')

Configuration for the proxy host's user name, port, password and private key can also be provided, separate from target host configuration.

.. code-block:: python

   hosts = [<..>]
   client = ParallelSSHClient(
                hosts, user='target_host_user',
                proxy_host='bastion',
                proxy_user='my_proxy_user',
                proxy_port=2222,
                proxy_pkey='proxy.key')

Where ``proxy.key`` is a filename containing private key to use for proxy host authentication.

In the above example, connections to the target hosts are made via SSH through ``my_proxy_user@bastion:2222`` -> ``target_host_user@<host>``.


Per Host Proxy Configuration
=============================

Proxy host can be configured in Per-Host Configuration:

.. code-block:: python

   hosts = [<..>]
   host_config = [
       HostConfig(proxy_host='127.0.0.1'),
       HostConfig(proxy_host='127.0.0.2'),
       HostConfig(proxy_host='127.0.0.3'),
       HostConfig(proxy_host='127.0.0.4'),
       ]
   client = ParallelSSHClient(hosts, host_config=host_config)
   output = client.run_command('echo me')

See :py:mod:`HostConfig <pssh.config.HostConfig>` for all possible configuration.

.. note::

   New tunneling implementation from `2.2.0` for best performance.

   Connecting to dozens or more hosts via a single proxy host will impact performance considerably.

   See above for using host specific proxy configuration.

Join and Output Timeouts
**************************

Clients have timeout functionality on reading output and ``client.join``.

Join timeout is applied to all parallel commands in total and is separate from ``ParallelSSHClient(timeout=<..>)`` which is applied to SSH session operations individually.

Timeout exceptions from ``join`` contain attributes for which commands have finished and which have not so client code can get output from any finished commands when handling timeouts.

.. code-block:: python

   from pssh.exceptions import Timeout

   output = client.run_command(..)
   try:
       client.join(output, timeout=5)
   except Timeout:
       pass

The client will raise a ``Timeout`` exception if *all* remote commands have not finished within five seconds in the above examples.


.. code-block:: python

   output = client.run_command(.., read_timeout=5)
   for host_out in output:
       try:
           for line in host_out.stdout:
	       print(line)
           for line in host_out.stderr:
	       print(line)
       except Timeout:
           pass


In the case of reading from output such as in the example above, timeout value is per output stream - meaning separate timeouts for stdout and stderr as well as separate timeout per host output.

*New in 1.5.0*

Reading Output from Partially Finished Commands
===============================================

Timeout exception when calling ``join`` has finished and unfinished commands as arguments.

This can be used to handle sets of commands that have finished and those that have not separately, for example to only gather output on finished commands to avoid blocking.

.. code-block:: python

   output = client.run_command(..)
   try:
       client.join(output, timeout=5)
   except Timeout as ex:
       # Some commands timed out
       finished_output = ex.args[2]
       unfinished_output = ex.args[3]
   else:
       # No timeout, all commands finished within five seconds
       finished_output = output
       unfinished_output = None
   for host_out in finished_output:
       for line in host_out.stdout:
           print(line)
   if unfinished_output is not None:
       <handle unfinished output>


In the above example, output is printed only for those commands which have completed within the five second timeout.

Client code may choose to then join again only on the unfinished output if some commands have failed in order to gather remaining output.

.. _partial-output:

Reading Partial Output of Commands That Do Not Terminate
==========================================================

In some cases, such as when the remote command never terminates unless interrupted, it is necessary to use PTY and to close the channel to force the process to be terminated before a ``join`` sans timeout can complete. For example:

.. code-block:: python

   output = client.run_command(
       'while true; do echo a line; sleep .1; done',
       use_pty=True, read_timeout=1)

   # Read as many lines of output as hosts have sent before the timeout
   stdout = []
   for host_out in output:
       try:
           for line in host_out.stdout:
               stdout.append(line)
       except Timeout:
           pass

   # Closing channel which has PTY has the effect of terminating
   # any running processes started on that channel.
   for host_out in output:
       host_out.client.close_channel(host_out.channel)
   # Join is not strictly needed here as channel has already been closed and
   # command has finished, but is safe to use regardless.
   client.join(output)
   # Can now read output up to when the channel was closed without blocking.
   rest_of_stdout = list(output[0].stdout)

Without a PTY, a ``join`` call with a timeout will complete with timeout exception raised but the remote process will be left running as per SSH protocol specifications.

.. note::

   Read timeout may be changed after ``run_command`` has been called by changing ``HostOutput.read_timeout`` for that particular host output.

.. note::

   When output from commands is not needed, it is best to use ``client.join(consume_output=True)`` so that output buffers are consumed automatically.

   If output is not read or automatically consumed by ``join`` output buffers will continually grow, resulting in increasing memory consumption while the client is running, though memory use rises very slowly.


Per-Host Configuration
***********************

Sometimes, different hosts require different configuration like user names and passwords, ports and private keys. Capability is provided to supply per host configuration for such cases.

.. code-block:: python

   from pssh.config import HostConfig

   hosts = ['localhost', 'localhost']
   host_config = [
       HostConfig(port=2222, user='user1',
                  password='pass', private_key='my_pkey.pem'),
       HostConfig(port=2223, user='user2',
                  password='pass', private_key='my_other_key.pem'),
   ]

   client = ParallelSSHClient(hosts, host_config=host_config)
   client.run_command('uname')
   <..>

In the above example, the client is configured to connect to hostname ``localhost``, port ``2222`` with username ``user1``, password ``pass`` and private key file ``my_pkey.pem`` and hostname ``localhost``, port ``2222`` with username ``user1``, password ``pass`` and private key file ``my_other_pkey.pem``.

When using ``host_config``, the number of ``HostConfig`` entries must match the number of hosts in ``client.hosts``. An exception is raised on client initialisation if not.

As of `2.10.0`, all client configuration can be provided in ``HostConfig``.

.. _per-host-cmds:

Per-Host Command substitution
******************************

For cases where different commands should be run on each host, or the same command with different arguments, functionality exists to provide per-host command arguments for substitution.

The ``host_args`` keyword parameter to :py:func:`run_command <pssh.clients.native.parallel.ParallelSSHClient.run_command>` can be used to provide arguments to use to format the command string.

Number of ``host_args`` items should be at least as many as number of hosts.

Any Python string format specification characters may be used in command string.


In the following example, first host in hosts list will use cmd ``host1_cmd`` second host ``host2_cmd`` and so on:

.. code-block:: python
   
   output = client.run_command('%s', host_args=('host1_cmd',
                                                'host2_cmd',
						'host3_cmd',))

Command can also have multiple arguments to be substituted.

.. code-block:: python

   output = client.run_command(
                '%s %s',
                host_args=(('host1_cmd1', 'host1_cmd2'),
                           ('host2_cmd1', 'host2_cmd2'),
                           ('host3_cmd1', 'host3_cmd2'),))

This expands to the following per host commands:

.. code-block:: bash

   host1: 'host1_cmd1 host1_cmd2'
   host2: 'host2_cmd1 host2_cmd2'
   host3: 'host3_cmd1 host3_cmd2'

A list of dictionaries can also be used as ``host_args`` for named argument substitution.

In the following example, first host in host list will use cmd ``echo command-0``, second host ``echo command-1`` and so on.

.. code-block:: python

   host_args = [{'cmd': 'echo command-%s' % (i,)}
                for i in range(len(client.hosts))]
   output = client.run_command('%(cmd)s', host_args=host_args)


This expands to the following per host commands:

.. code-block:: bash

   host1: 'echo command-0'
   host2: 'echo command-1'
   host3: 'echo command-2'


Run command features and options
*********************************

See :py:func:`run_command API documentation <pssh.clients.native.parallel.ParallelSSHClient.run_command>` for a complete list of features and options.

Run with sudo
===============

``parallel-ssh`` can be instructed to run its commands under ``sudo``:

.. code-block:: python

   client = <..>
   
   output = client.run_command(<..>, sudo=True)
   client.join(output)

While not best practice and password-less ``sudo`` is best configured for a limited set of commands, a sudo password may be provided via the stdin channel:

.. code-block:: python

   client = <..>
   
   output = client.run_command(<..>, sudo=True)
   for host_out in output:
       host_out.stdin.write('my_password\n')
       host_out.stdin.flush()
   client.join(output)
   
.. note::

   Note the inclusion of the new line ``\n`` when using sudo with a password.


Run with configurable shell
============================

By default the client will use the login user's shell to execute commands per the SSH protocol.

Shell to use is configurable:

.. code-block:: python

   client = <..>
   
   output = client.run_command(<..>, shell='zsh -c')
   for host_out in output;
       for line in host_out.stdout:
           print(line)

Commands will be run under the ``zsh`` shell in the above example. The command string syntax of the shell must be used, typically ``<shell> -c``.


Output And Command Encoding
===========================

By default, command string and output are encoded as ``UTF-8``. This can be configured with the ``encoding`` keyword argument to ``run_command`` and ``open_shell``.

.. code-block:: python

   client = ParallelSSHClient(<..>)

   cmd = b"echo \xbc".decode('latin-1')
   output = client.run_command(cmd, encoding='latin-1')
   stdout = list(output[0].stdout)


Contents of ``stdout`` are `latin-1` decoded.

``cmd`` string is also `latin-1` encoded when running command or writing to interactive shell.

Output encoding can also be changed by adjusting ``HostOutput.encoding``.

.. code-block:: python

   client = ParallelSSHClient(<..>)

   output = client.run_command('echo me')
   output[0].encoding = 'utf-16'
   stdout = list(output[0].stdout)

Contents of ``stdout`` are `utf-16` decoded.


.. note::

   Encoding must be valid `Python codec <https://docs.python.org/3/library/codecs.html>`_


Enabling use of pseudo terminal emulation
===========================================

Pseudo Terminal Emulation (PTY) can be enabled when running commands, defaults to off.

Enabling it has some side effects on the output and behaviour of commands such as combining stdout and stderr output - see `bash` man page for more information.

All output, including stderr, is sent to the ``stdout`` channel with PTY enabled.

.. code-block:: python

   client = <..>

   output = client.run_command("echo 'asdf' >&2", use_pty=True)
   for line in output[0].stdout:
       print(line)


Note output is from the ``stdout`` channel while it was written to ``stderr``.

:Output:
   .. code-block:: shell

      asdf

Stderr is empty:

.. code-block:: python
   
   for line in output[0].stderr:
       print(line)

No output from ``stderr``.

.. _sftp-scp:

SFTP and SCP
*************

SFTP and SCP are both supported by ``parallel-ssh`` and functions are provided by the client for copying files to and from remote servers - default native clients only.

Neither SFTP nor SCP have a shell interface and no output is sent for any SFTP/SCP commands.

As such, SFTP/SCP functions in ``ParallelSSHClient`` return greenlets that will need to be joined to raise any exceptions from them. :py:func:`gevent.joinall` may be used for that.


Copying files to remote hosts in parallel
===========================================

To copy the local file with relative path ``../test`` to the remote relative path ``test_dir/test`` - remote directory will be created if it does not exist, permissions allowing. ``raise_error=True`` instructs ``joinall`` to raise any exceptions thrown by the greenlets.

.. code-block:: python

   from pssh.clients import ParallelSSHClient
   from gevent import joinall
   
   client = ParallelSSHClient(hosts)
   
   cmds = client.copy_file('../test', 'test_dir/test')
   joinall(cmds, raise_error=True)

To recursively copy directory structures, enable the ``recurse`` flag:

.. code-block:: python

   cmds = client.copy_file('my_dir', 'my_dir', recurse=True)
   joinall(cmds, raise_error=True)

.. seealso::

   :py:func:`copy_file <pssh.clients.native.parallel.ParallelSSHClient.copy_file>` API documentation and exceptions raised.

   :py:func:`gevent.joinall` Gevent's ``joinall`` API documentation.

Copying files from remote hosts in parallel
===========================================

Copying remote files in parallel requires that file names are de-duplicated otherwise they will overwrite each other. ``copy_remote_file`` names local files as ``<local_file><suffix_separator><host>``, suffixing each file with the host name it came from, separated by a configurable character or string.

.. code-block:: python

   from pssh.pssh_client import ParallelSSHClient
   from gevent import joinall
   
   client = ParallelSSHClient(hosts)
   
   cmds = client.copy_remote_file('remote.file', 'local.file')
   joinall(cmds, raise_error=True)

The above will create files ``local.file_host1`` where ``host1`` is the host name the file was copied from.

.. _copy-args:

Configurable per host Filenames
=================================

File name arguments, for both local and remote files and for copying to and from remote hosts, can be configured on a per-host basis similarly to `host arguments <#per-host-cmds>`_ in ``run_command``.

Example shown applies to all file copy functionality, all of ``scp_send``, ``scp_recv``, ``copy_file`` and ``copy_remote_file``.

For example, to copy the local files ``['local_file_1', 'local_file_2']`` as remote files ``['remote_file_1', 'remote_file_2']`` on the two hosts ``['host1', 'host2']``

.. code-block:: python

   hosts = ['host1', 'host2']
   
   client = ParallelSSHClient(hosts)

   copy_args = [{'local_file': 'local_file_1',
                 'remote_file': 'remote_file_1',
                 },
                {'local_file': 'local_file_2',
                 'remote_file': 'remote_file_2',
                 }]
   cmds = client.copy_file('%(local_file)s', '%(remote_file)s',
                           copy_args=copy_args)
   joinall(cmds)

The client will copy ``local_file_1`` to ``host1`` as ``remote_file_1`` and ``local_file_2`` to ``host2`` as ``remote_file_2``.

Each item in ``copy_args`` list should be a dictionary as shown above. Number of items in ``copy_args`` must match length of ``client.hosts`` if provided or exception will be raised.

``copy_remote_file``, ``scp_send`` and ``scp_recv`` may all be used in the same manner to configure remote and local file names per host.

.. seealso::

   :py:func:`copy_remote_file <pssh.clients.native.parallel.ParallelSSHClient.copy_remote_file>`  API documentation and exceptions raised.

Single host copy
==================

If wanting to copy a file from a single remote host and retain the original filename, can use the single host :py:class:`SSHClient <pssh.clients.native.single.SSHClient>` and its :py:func:`copy_remote_file <pssh.clients.native.single.SSHClient.copy_remote_file>` directly.

.. code-block:: python

   from pssh.clients import SSHClient

   client = SSHClient('localhost')
   client.copy_remote_file('remote_filename', 'local_filename')
   client.scp_recv('remote_filename', 'local_filename')

.. seealso::

   :py:func:`SSHClient.copy_remote_file <pssh.clients.native.single.SSHClient.copy_remote_file>`  API documentation and exceptions raised.


Interactive Shells
******************

Interactive shells can be used to run commands, as an alternative to ``run_command``.

This is best used in cases where wanting to run multiple commands per host on the same channel with combined output.

.. code-block:: python

   client = ParallelSSHClient(<..>)

   cmd = """
   echo me
   echo me too
   """

   shells = client.open_shell()
   client.run_shell_commands(shells, cmd)
   client.join_shells(shells)

   for shell in shells:
       for line in shell.stdout:
           print(line)
       print(shell.exit_code)


Running Commands On Shells
==========================

Command to run can be multi-line, a single command or a list of commands.

Shells provided are used for all commands, reusing the channel opened by ``open_shell``.


Multi-line Commands
-------------------

Multi-line commands or command string is executed as-is.

.. code-block:: python

   client = ParallelSSHClient(<..>)

   cmd = """
   echo me
   echo me too
   """

   shells = client.open_shell()
   client.run_shell_commands(shells, cmd)


Single And List Of Commands
---------------------------

A single command can be used, as well as a list of commands to run on each shell.

.. code-block:: python

   cmd = 'echo me three'
   client.run_shell_commands(shells, cmd)

   cmd = ['echo me also', 'echo and as well me', 'exit 1']
   client.run_shell_commands(shells, cmd)


Waiting For Completion
======================

Joining shells waits for running commands to complete and closes shells.

This allows output to be read up to the last command executed without blocking.

.. code-block:: python

   client.join_shells(shells)

Joined on shells are closed and may not run any further commands.

Trying to use the same shells after ``join_shells`` will raise :py:class:`pssh.exceptions.ShellError`.


Reading Shell Output
====================

Output for each shell includes all commands executed.

.. code-block:: python

   for shell in shells:
       stdout = list(shell.stdout)
       exit_code = shell.exit_code


Exit code is for the *last executed command only* and can be retrieved when ``run_shell_commands`` has been used at least once.

Each shell also has a ``shell.output`` which is a :py:class:`HostOutput <pssh.output.HostOutput>` object. ``shell.stdout`` et al are the same as ``shell.output.stdout``.


Reading Partial Shell Output
----------------------------

Reading output will **block indefinitely** prior to join being called. Use ``read_timeout`` in order to read partial output.

.. code-block:: python

   shells = client.open_shell(read_timeout=1)
   client.run_shell_commands(shells, ['echo me'])

   # Times out after one second
   for line in shells[0].stdout:
       print(line)


Join Timeouts
=============

Timeouts on ``join_shells`` can be done similarly to ``join``.

.. code-block:: python

   cmds = ["echo me", "sleep 1.2"]

   shells = client.open_shell()
   client.run_shell_commands(shells, cmds)
   client.join_shells(shells, timeout=1)


Single Clients
==============

On single clients shells can be used as a context manager to join and close the shell on exit.

.. code-block:: python

   client = SSHClient(<..>)

   cmd = 'echo me'
   with client.open_shell() as shell:
       shell.run(cmd)
   print(list(shell.stdout))
   print(shell.exit_code)


Or explicitly:

.. code-block:: python

   cmd = 'echo me'
   shell = client.open_shell()
   shell.run(cmd)
   shell.close()

Closing a shell also waits for commands to complete.


.. seealso::

   :py:class:`pssh.clients.base.single.InteractiveShell` for more documentation.

   * :py:func:`open_shell() <pssh.clients.base.parallel.BaseParallelSSHClient.open_shell>`
   * :py:func:`run_shell_commands() <pssh.clients.base.parallel.BaseParallelSSHClient.run_shell_commands>`
   * :py:func:`join_shells() <pssh.clients.base.parallel.BaseParallelSSHClient.join_shells>`



Hosts filtering and overriding
*******************************

Iterators and filtering
========================

Any type of iterator may be used as hosts list, including generator and list comprehension expressions.

:List comprehension:

   .. code-block:: python

      hosts = ['dc1.myhost1', 'dc2.myhost2']
      client = ParallelSSHClient([h for h in hosts if h.find('dc1')])

:Generator:

   .. code-block:: python

      hosts = ['dc1.myhost1', 'dc2.myhost2']
      client = ParallelSSHClient((h for h in hosts if h.find('dc1')))

:Filter:

   .. code-block:: python

      hosts = ['dc1.myhost1', 'dc2.myhost2']
      client = ParallelSSHClient(filter(lambda h: h.find('dc1'), hosts))
      client.run_command(<..>)

.. note ::

    Assigning a generator to host list is possible as shown above, and the generator is consumed into a list on assignment.

    Multiple calls to ``run_command`` will use the same hosts read from the provided generator.


Overriding hosts list
=======================

Hosts list can be modified in place.

A call to ``run_command`` will create new connections as necessary and output will only be returned for the hosts ``run_command`` executed on.

Clients for hosts that are no longer on the host list are removed on host list assignment. Reading output from hosts removed from host list is feasible, as long as their output objects or interactive shells are in scope.


.. code-block:: python

   client = <..>

   client.hosts = ['otherhost']
   print(client.run_command('exit 0'))
       <..>
       host='otherhost'
       exit_code=None
       <..>


When reassigning host list frequently, it is best to sort or otherwise ensure order is maintained to avoid reconnections on hosts that are still in the host list but in a different position.

For example, the following will cause reconnections on both hosts, though both are still in the list.

.. code-block:: python

   client.hosts = ['host1', 'host2']
   client.hosts = ['host2', 'host1']


In such cases it would be best to maintain order to avoid reconnections. This is also true when adding or removing hosts in host list.

No change in clients occurs in the following case.

.. code-block:: python

   client.hosts = sorted(['host1', 'host2'])
   client.hosts = sorted(['host2', 'host1'])


Clients for hosts that would be removed by a reassignment can be calculated with:

.. code-block:: python

   set(enumerate(client.hosts)).difference(
       set(enumerate(new_hosts)))


IPv6 Addresses
***************

All clients support IPv6 addresses in both host list, and via DNS. Typically IPv4 addresses are preferred as they are
the first entries in DNS resolution depending on DNS server configuration and entries.

The ``ipv6_only`` flag may be used to override this behaviour and force the client(s) to only choose IPv6 addresses, or
raise an error if none are available.

Connecting to localhost via an IPv6 address.

.. code-block:: python

   client = ParallelSSHClient(['::1'])
   <..>

Asking client to only use IPv6 for DNS resolution.
:py:class:`NoIPv6AddressFoundError <pssh.exceptions.NoIPv6AddressFoundError>` is raised if no IPv6 address is available
for hosts.

.. code-block:: python

   client = ParallelSSHClient(['myhost.com'], ipv6_only=True)
   output = client.run_command('echo me')

Similarly for single clients.

.. code-block:: python

   client = SSHClient(['myhost.com'], ipv6_only=True)

For choosing a mix of IPv4/IPv6 depending on the host name, developers can use `socket.getaddrinfo` directly and pick
from available addresses.

*New in 2.7.0*
