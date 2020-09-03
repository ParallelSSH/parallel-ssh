Advanced Usage
###############

There are several more advanced usage features of ``parallel-ssh``, such as tunnelling (aka proxying) via an intermediate SSH server and per-host configuration and command substitution among others.

Agents and Private Keys
************************

Programmatic Private Keys
============================

By default, ``parallel-ssh`` will attempt to use loaded keys in an available SSH agent as well as default identity files under the user's home directory.

See `IDENTITIES` in :py:class:`SSHClient <pssh.clients.base_ssh_client.BaseSSHClient>` for a list of identity files.

A private key can also be provided programmatically.

.. code-block:: python

   import os

   from pssh.clients import ParallelSSHClient

   client = ParallelSSHClient(hosts, pkey=os.path.expanduser("~/.ssh/my_key"))

Where ``my_key`` is a private key file under `.ssh` in the user's home directory.


Native clients
***************

ssh2-python (libssh2)
=====================

Starting from version ``1.2.0``, the default client in ``parallel-ssh`` is based on `ssh2-python` (`libssh2`). It is a native client, offering C level performance with an easy to use Python API.

See `this post <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_ for a performance comparison of the available clients in the `1.x.x` series.


.. code-block:: python

   from pssh.clients import ParallelSSHClient

   hosts = ['my_host', 'my_other_host']
   client = ParallelSSHClient(hosts)

   output = client.run_command('uname')
   for host_out in output:
       for line in host_out.stdout:
           print(line)


.. seealso::

   `Feature comparison <clients.html>`_ for how the `2.x.x` client features compare.

   API documentation for `parallel <native_parallel.html>`_ and `single <native_single.html>`_ native clients.


ssh-python (libssh) Client
============================

From version `1.12.0` another client based on `libssh <https://libssh.org>`_ via `ssh-python` is provided for testing purposes.

The API is similar to the default client, while ``ssh-python`` offers more supported authentication methods compared to the default client.

On the other hand, this client lacks SCP, SFTP and proxy functionality.

.. code-block:: python

   from pssh.clients.ssh import ParallelSSHClient

   hosts = ['localhost', 'localhost']
   client = ParallelSSHClient(hosts)

   output = client.run_command('uname')
   client.join(output)
   for host_out in output:
       for line in host_out.stdout:
           print(line)


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


``ssh-python`` :py:class:`ParallelSSHClient <pssh.clients.ssh.ParallelSSHClient>` only.


Tunneling
===========

This is used in cases where the client does not have direct access to the target host and has to authenticate via an intermediary, also called a bastion host, commonly used for additional security as only the bastion host needs to have access to the target host.

ParallelSSHClient       ------>        Proxy host         -------->         Target host

Proxy host can be configured as follows in the simplest case:

.. code-block:: python

  hosts = [<..>]
  client = ParallelSSHClient(hosts, proxy_host='bastion')

Configuration for the proxy host's user name, port, password and private key can also be provided, separate from target host configuration.

.. code-block:: python
   
   hosts = [<..>]
   client = ParallelSSHClient(hosts, user='target_host_user', 
                              proxy_host='bastion', proxy_user='my_proxy_user',
 			      proxy_port=2222, 
 			      proxy_pkey='proxy.key')

Where ``proxy.key`` is a filename containing private key to use for proxy host authentication.

In the above example, connections to the target hosts are made via SSH through ``my_proxy_user@bastion:2222`` -> ``target_host_user@<host>``.

.. note::

   Proxy host connections are asynchronous and use the SSH protocol's native TCP tunneling - aka local port forward. No external commands or processes are used for the proxy connection, unlike the `ProxyCommand` directive in OpenSSH and other utilities.

   While connections initiated by ``parallel-ssh`` are asynchronous, connections from proxy host -> target hosts may not be, depending on SSH server implementation. If only one proxy host is used to connect to a large number of target hosts and proxy SSH server connections are *not* asynchronous, this may adversely impact performance on the proxy host.

Join and Output Timeouts
**************************

The native clients have timeout functionality on reading output and ``client.join``. These is a timeout on the parallel commands as a whole and is separate from ``ParallelSSHClient(timeout=<..>)`` which is applied to each SSH session individually.

Timeout exceptions contain attributes for which commands have finished and which have not so client code can get output from any finished commands when handling timeouts.

.. code-block:: python

   from pssh.exceptions import Timeout

   output = client.run_command(..)
   try:
       client.join(output, timeout=5)
   except Timeout:
       pass

.. code-block:: python

   output = client.run_command(.., timeout=5)
   for host, host_out in output.items():
       try:
           for line in host_out.stdout:
	       pass
           for line in host_out.stderr:
	       pass
       except Timeout:
           pass


The client will raise a ``Timeout`` exception if all remote commands have not finished within five seconds in the above examples.

In the case of reading from output, timeout value is per output stream - meaning separate timeouts for stdout and stderr.

*New in 1.5.0*

Distinguishing between finished and unfinished commands
--------------------------------------------------------

Commands that timed out before finishing can be distinguished by calling ``SSHClient.finished`` on them. This is a non-blocking function and does not use the network.

<example>

*New in 2.0.0*

Reading Partial Output of Commands That Do Not Terminate
==========================================================

In some cases, such as when the remote command never terminates unless interrupted, it is necessary to use PTY and to close the channel to force the process to be terminated before a ``join`` sans timeout can complete. For example:

.. code-block:: python

   output = client.run_command('tail -f /var/log/messages', use_pty=True, timeout=1)

   # Read as many lines of output as server has sent before the timeout
   stdout = []
   for host, host_out in output.items():
       for host, host_out in output.items():
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

Without a PTY, a ``join`` call with a timeout will complete with timeout exception raised but the remote process will be left running as per SSH protocol specifications.

Furthermore, once reading output has timed out, it is necessary to restart the output generators as by Python design they only iterate once. This can be done as follows:

.. code-block:: python

   output = client.run_command(<..>, timeout=1)
   for host_out in output:
       try:
           stdout = list(host_out.stdout)
       except Timeout:
           client.reset_output_generators(host_out)

Generator reset shown above is also performed automatically by calls to ``join`` and does not need to be done manually when ``join`` is used after output reading.

.. note::

   ``join`` with a timeout forces output to be consumed as otherwise the pending output will keep the channel open and make it appear as if command has not yet finished.

   To capture output when using ``join`` with a timeout, gather output first before calling ``join``, making use of output timeout as well, and/or make use of :ref:`host logger` functionality.


Per-Host Configuration
***********************

Sometimes, different hosts require different configuration like user names and passwords, ports and private keys. Capability is provided to supply per host configuration for such cases.

.. code-block:: python

   from pssh.config import HostConfig

   hosts = ['localhost', 'localhost']
   host_config = [
       HostConfig(port=2222, user='user1', password='pass', private_key='my_pkey.pem'),
       HostConfig(port=2223, user='user2', password='pass', private_key='my_other_key.pem')
   ]

   client = ParallelSSHClient(hosts, host_config=host_config)
   client.run_command('uname')
   <..>

In the above example, the client is configured to connect to hostname ``localhost``, port ``2222`` with username ``user1``, password ``pass`` and private key file ``my_pkey.pem`` and hostname ``localhost``, port ``2222`` with username ``user1``, password ``pass`` and private key file ``my_other_pkey.pem``.


.. note::

   Currently only ``port``, ``user``, ``password`` and ``private_key`` ``HostConfig`` values are used.

.. note::

   Proxy host configuration is currently per ``ParallelSSHClient`` and cannot yet be provided via per-host configuration.
   Multiple clients can be used to make use of multiple proxy hosts.

   This feature will be provided in future releases.

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

In the following example, first host in host list will use cmd ``echo command-1``, second host ``echo command-2`` and so on.

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

.. note::

   With a PTY, the default, stdout and stderr output is combined into stdout.

   Without a PTY, separate output is given for stdout and stderr, although some programs and server configurations require a PTY.

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
   for host in output:
       stdin = output[host].stdin
       stdin.write('my_password\n')
       stdin.flush()
   client.join(output)
   
.. note::

   Note the inclusion of the new line ``\n`` when using sudo with a password.


Output encoding
===============

By default, output is encoded as ``UTF-8``. This can be configured with the ``encoding`` keyword argument.

.. code-block:: python

   client = <..>

   client.run_command(<..>, encoding='utf-16')
   stdout = list(output[0].stdout)

Contents of ``stdout`` are `UTF-16` encoded.

.. note::

   Encoding must be valid `Python codec <https://docs.python.org/2.7/library/codecs.html>`_

Enabling use of pseudo terminal emulation
===========================================

Pseudo Terminal Emulation (PTY) can be enabled when running commands. Enabling it has some side effects on the output and behaviour of commands such as combining stdout and stderr output - see bash man page for more information.

All output, including stderr, is sent to the `stdout` channel with PTY enabled.

.. code-block:: python

   client = <..>

   client.run_command("echo 'asdf' >&2", use_pty=True)
   for line in output[0].stdout:
       print(line)


Note output is from the ``stdout`` channel while it was writeen to ``stderr``.

:Output:
   .. code-block:: shell

      asdf

Stderr is empty:

.. code-block:: python
   
   for line in output[client.hosts[0]].stderr:
       print(line)

No output from ``stderr``.

SFTP and SCP
*************

SFTP and SCP are supported by ``parallel-ssh`` and functions are provided by the client for copying files with SFTP to and from remote servers.

Neither SFTP nor SCP have a shell interface and no output is provided for any SFTP/SCP commands.

As such, SFTP functions in ``ParallelSSHClient`` return greenlets that will need to be joined to raise any exceptions from them. :py:func:`gevent.joinall` may be used for that.


Copying files to remote hosts in parallel
===========================================

To copy the local file with relative path ``../test`` to the remote relative path ``test_dir/test`` - remote directory will be created if it does not exist, permissions allowing. ``raise_error=True`` instructs ``joinall`` to raise any exceptions thrown by the greenlets.

.. code-block:: python

   from pssh.clients import ParallelSSHClient
   from gevent import joinall
   
   client = ParallelSSHClient(hosts)
   
   greenlets = client.copy_file('../test', 'test_dir/test')
   joinall(greenlets, raise_error=True)

To recursively copy directory structures, enable the ``recurse`` flag:

.. code-block:: python

   greenlets = client.copy_file('my_dir', 'my_dir', recurse=True)
   joinall(greenlets, raise_error=True)

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
   
   greenlets = client.copy_remote_file('remote.file', 'local.file')
   joinall(greenlets, raise_error=True)

The above will create files ``local.file_host1`` where ``host1`` is the host name the file was copied from.

Configurable per host Filenames
--------------------------------

``copy arg`` example.

.. seealso::

   :py:func:`copy_remote_file <pssh.clients.native.parallel.ParallelSSHClient.copy_remote_file>`  API documentation and exceptions raised.

Single host copy
==================

If wanting to copy a file from a single remote host and retain the original filename, can use the single host :py:class:`SSHClient <pssh.clients.native.single.SSHClient>` and its :py:func:`copy_remote_file <pssh.clients.native.single.SSHClient.copy_remote_file>` directly.

.. code-block:: python

   from pssh.clients import SSHClient

   client = SSHClient('localhost')
   client.copy_remote_file('remote_filename', 'local_filename')

.. seealso::

   :py:func:`SSHClient.copy_remote_file <pssh.clients.native.single.SSHClient.copy_remote_file>`  API documentation and exceptions raised.


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

    Since generators by design only iterate over a sequence once then stop, ``client.hosts`` should be re-assigned after each call to ``run_command`` when using generators as target of ``client.hosts``.

Overriding hosts list
=======================

Hosts list can be modified in place. A call to ``run_command`` will create new connections as necessary and output will only contain output for the hosts ``run_command`` executed on.

.. code-block:: python

   client = <..>

   client.hosts = ['otherhost']
   print(client.run_command('exit 0'))
       host='otherhost'
       exit_code=None
       <..>
