Advanced Usage
=================

There are several more advanced usage features of ``parallel-ssh``, such as tunnelling (aka proxying) via an intermediate SSH server and per-host configuration and command substitution among others.

Agents and Private Keys
*************************

SSH Agent forwarding
-----------------------

SSH agent forwarding, what ``ssh -A`` does on the command line, is supported and enabled by default. Creating a client object as:

.. code-block:: python

   ParallelSSHClient(hosts, forward_ssh_agent=False)

will disable this behaviour.

Programmatic Private Keys
--------------------------

By default, ``parallel-ssh`` will use all keys in an available SSH agent and identity keys under the user's SSH directory - ``id_rsa``, ``id_dsa`` and ``identity`` in ``~/.ssh``.

A private key can also be provided programmatically.

.. code-block:: python

  from pssh.utils import load_private_key
  from pssh.pssh_client import ParallelSSHClient

  client = ParallelSSHClient(hosts, pkey=load_private_key('my_key'))

Where ``my_key`` is a private key file in current working directory.

The helper function :py:func:`load_private_key <pssh.utils.load_private_key>` will attempt to load all available key types and raises :mod:`SSHException <pssh.exceptions.SSHException>` if it cannot load the key file.

.. seealso::

   :py:func:`load_private_key <pssh.utils.load_private_key>`

Disabling use of system SSH Agent
----------------------------------

Use of an available SSH agent can also be disabled.

.. code-block:: python

  client = ParallelSSHClient(hosts, pkey=load_private_key('my_key'), 
                             allow_agent=False)

.. warning::

   For large number of hosts, it is recommended that private keys are provided programmatically and use of SSH agent is disabled via ``allow_agent=False`` as above. 

   If the number of hosts is large enough, available connections to the system SSH agent may be exhausted which will stop the client from working on a subset of hosts.

   This is a limitation of the underlying SSH client used by ``parallel-ssh``.

Programmatic SSH Agent
-----------------------

*Paramiko client only*.

It is also possible to programmatically provide an SSH agent for the client to use, instead of a system provided one. This is useful in cases where hosts need different private keys and a system SSH agent is not available.

.. code-block:: python
   
   from pssh.agent import SSHAgent
   from pssh.utils import load_private_key
   from pssh.clients.miko import ParallelSSHClient

   agent = SSHAgent()
   agent.add_key(load_private_key('my_private_key_filename'))
   agent.add_key(load_private_key('my_other_private_key_filename'))
   hosts = ['my_host', 'my_other_host']

   client = ParallelSSHClient(hosts, agent=agent)
   client.run_command(<..>)

.. note::

   Supplying an agent programmatically implies that a system SSH agent will *not* be used even if available.

.. seealso::

   :py:class:`pssh.agent.SSHAgent`


Native clients
*****************

Starting from version ``1.2.0``, a new client is supported in ``parallel-ssh`` which offers much greater performance and reduced overhead than the current default client.

The new client is based on ``libssh2`` via the ``ssh2-python`` extension library and supports non-blocking mode natively. Binary wheel packages with ``libssh2`` included are provided for Linux, OSX and Windows platforms and all supported Python versions.

See `this post <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_ for a performance comparison of the available clients.

To make use of this new client, ``ParallelSSHClient`` can be imported from ``pssh.clients.native`` instead. Their respective APIs are almost identical. 

.. code-block:: python

  from pssh.clients.native import ParallelSSHClient

  hosts = ['my_host', 'my_other_host']
  client = ParallelSSHClient(hosts)
  client.run_command(<..>)


.. seealso::

   `Feature comparison <ssh2.html>`_ for how the client features compare.

   API documentation for `parallel <native_parallel.html>`_ and `single <native_single.html>`_ native clients.

Tunneling
**********

This is used in cases where the client does not have direct access to the target host and has to authenticate via an intermediary, also called a bastion host, commonly used for additional security as only the bastion host needs to have access to the target host.

ParallelSSHClient       ------>        Proxy host         -------->         Target host

Proxy host can be configured as follows in the simplest case:

.. code-block:: python

  hosts = [<..>]
  client = ParallelSSHClient(hosts, proxy_host='bastion')
  
Configuration for the proxy host's user name, port, password and private key can also be provided, separate from target host user name.

.. code-block:: python
   
   from pssh.utils import load_private_key
   
   hosts = [<..>]
   client = ParallelSSHClient(hosts, user='target_host_user', 
                              proxy_host='bastion', proxy_user='my_proxy_user',
 			      proxy_port=2222, 
 			      proxy_pkey=load_private_key('proxy.key'))

Where ``proxy.key`` is a filename containing private key to use for proxy host authentication.

In the above example, connections to the target hosts are made via SSH through ``my_proxy_user@bastion:2222`` -> ``target_host_user@<host>``.

.. note::

   Proxy host connections are asynchronous and use the SSH protocol's native TCP tunneling - aka local port forward. No external commands or processes are used for the proxy connection, unlike the `ProxyCommand` directive in OpenSSH and other utilities.

   While connections initiated by ``parallel-ssh`` are asynchronous, connections from proxy host -> target hosts may not be, depending on SSH server implementation. If only one proxy host is used to connect to a large number of target hosts and proxy SSH server connections are *not* asynchronous, this may adversely impact performance on the proxy host.

Join and Output Timeouts
**************************

*New in 1.5.0*

The native clients have timeout functionality on reading output and ``client.join``.

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

The client will raise a ``Timeout`` exception if remote commands have not finished within five seconds in the above examples.

Reading Partial Output of Commands That Do Not Terminate
----------------------------------------------------------

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
   for host, host_out in output.items():
       client.host_clients[host].close_channel(host_out.channel)
   # Join is not strictly needed here as channel has already been closed and
   # command has finished, but is safe to use regardless.
   client.join(output)

Without a PTY, a ``join`` call with a timeout will complete with timeout exception raised but the remote process will be left running as per SSH protocol specifications.

Furthermore, once reading output has timed out, it is necessary to restart the output generators as by Python design they only iterate once. This can be done as follows:

.. code-block:: python

   output = client.run_command(<..>, timeout=1)
   for host, host_out in output.items():
       try:
           stdout = list(host_out.stdout)
       except Timeout:
           client.reset_output_generators(host_out)

Generator reset shown above is also performed automatically by calls to ``join`` and does not need to be done manually when ``join`` is used after output reading.

.. note::

   ``join`` with a timeout forces output to be consumed as otherwise the pending output will keep the channel open and make it appear as if command has not yet finished.

   To capture output when using ``join`` with a timeout, gather output first before calling ``join``, making use of output timeout as well, and/or make use of :ref:`host logger` functionality.


.. warning::

   Beware of race conditions when using timeout functionality. For best results, only send one command per call to ``run_command`` when using timeout functionality.

   As the timeouts are performed on ``select`` calls on the socket which is responsible for all client <-> server communication, whether or not a timeout will occur depends on what the socket is doing at that time.

   Multiple commands like ``run_command('echo blah; sleep 5')`` where ``sleep 5`` is a placeholder for something taking five seconds to complete will result in a race condition as the second command may or may not have started by the time ``join`` is called or output is read which will cause timeout to *not* be raised even if the second command has not started or completed.

   It is responsibility of developer to avoid these race conditions such as by only sending one command in such cases.


Per-Host Configuration
***********************

Sometimes, different hosts require different configuration like user names and passwords, ports and private keys. Capability is provided to supply per host configuration for such cases.

.. code-block:: python

   from pssh.utils import load_private_key

   host_config = {'host1' : {'user': 'user1', 'password': 'pass',
                             'port': 2222,
                             'private_key': 'my_key.pem'},
                  'host2' : {'user': 'user2', 'password': 'pass',
		             'port': 2223,
			     'private_key': 'my_other_key.pem'},
		 }
   hosts = host_config.keys()

   client = ParallelSSHClient(hosts, host_config=host_config)
   client.run_command('uname')
   <..>

In the above example, ``host1`` will use user name ``user1`` and private key from ``my_key.pem`` and ``host2`` will use user name ``user2`` and private key from ``my_other_key.pem``.

.. note::

   Proxy host configuration is per `ParallelSSHClient` and cannot be provided via per-host configuration.
   Multiple clients can be used to make use of multiple proxy hosts.

Per-Host Command substitution
******************************

For cases where different commands should be run on each host, or the same command with different arguments, functionality exists to provide per-host command arguments for substitution.

The ``host_args`` keyword parameter to :py:func:`run_command <pssh.pssh_client.ParallelSSHClient.run_command>` can be used to provide arguments to use to format the command string.

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

See :py:func:`run_command API documentation <pssh.pssh_client.ParallelSSHClient.run_command>` for a complete list of features and options.

.. note::

   With a PTY, the default, stdout and stderr output is combined into stdout.

   Without a PTY, separate output is given for stdout and stderr, although some programs and server configurations require a PTY.

Run with sudo
---------------

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

Output encoding
-----------------

By default, output is encoded as ``UTF-8``. This can be configured with the ``encoding`` keyword argument.

.. code-block:: python

   client = <..>

   client.run_command(<..>, encoding='utf-16')
   stdout = list(output[client.hosts[0]].stdout)

Contents of ``stdout`` will be `UTF-16` encoded.

.. note::

   Encoding must be valid `Python codec <https://docs.python.org/2.7/library/codecs.html>`_

Disabling use of pseudo terminal emulation
--------------------------------------------

For cases where use of a `PTY` is not wanted, such as having separate stdout and stderr outputs, the remote command is a daemon that needs to fork and detach itself or when use of a shell is explicitly disabled, use of PTY can also be disabled.

The following example prints to stderr with PTY disabled.

.. code-block:: python

   from __future__ import print_function

   client = <..>

   client.run_command("echo 'asdf' >&2", use_pty=False)
   for line in output[client.hosts[0]].stderr: 
       print(line)

:Output:
   .. code-block:: shell

      asdf

Combined stdout/stderr
-----------------------

With a PTY on the paramiko client, stdout and stderr output is combined.

The same example as above with a PTY:

.. code-block:: python

   from __future__ import print_function

   client = <..>

   client.run_command("echo 'asdf' >&2")
   for line in output[client.hosts[0]].stdout: 
       print(line)

Note output is now from the ``stdout`` channel.

:Output:
   .. code-block:: shell

      asdf

Stderr is empty:

.. code-block:: python
   
   for line in output[client.hosts[0]].stderr:
       print(line)

No output from ``stderr``.

SFTP
*****

SFTP - `SCP version 2` - is supported by ``parallel-ssh`` and two functions are provided by the client for copying files with SFTP.

SFTP does not have a shell interface and no output is provided for any SFTP commands.

As such, SFTP functions in ``ParallelSSHClient`` return greenlets that will need to be joined to raise any exceptions from them. :py:func:`gevent.joinall` may be used for that.


Copying files to remote hosts in parallel
----------------------------------------------

To copy the local file with relative path ``../test`` to the remote relative path ``test_dir/test`` - remote directory will be created if it does not exist, permissions allowing. ``raise_error=True`` instructs ``joinall`` to raise any exceptions thrown by the greenlets.

.. code-block:: python

   from pssh.pssh_client import ParallelSSHClient
   from gevent import joinall
   
   client = ParallelSSHClient(hosts)
   
   greenlets = client.copy_file('../test', 'test_dir/test')
   joinall(greenlets, raise_error=True)

To recursively copy directory structures, enable the ``recurse`` flag:

.. code-block:: python

   greenlets = client.copy_file('my_dir', 'my_dir', recurse=True)
   joinall(greenlets, raise_error=True)

.. seealso::

   :py:func:`copy_file <pssh.pssh_client.ParallelSSHClient.copy_file>` API documentation and exceptions raised.

   :py:func:`gevent.joinall` Gevent's ``joinall`` API documentation.

Copying files from remote hosts in parallel
----------------------------------------------

Copying remote files in parallel requires that file names are de-duplicated otherwise they will overwrite each other. ``copy_remote_file`` names local files as ``<local_file><suffix_separator><host>``, suffixing each file with the host name it came from, separated by a configurable character or string.

.. code-block:: python

   from pssh.pssh_client import ParallelSSHClient
   from gevent import joinall
   
   client = ParallelSSHClient(hosts)
   
   greenlets = client.copy_remote_file('remote.file', 'local.file')
   joinall(greenlets, raise_error=True)

The above will create files ``local.file_host1`` where ``host1`` is the host name the file was copied from.

.. seealso::

   :py:func:`copy_remote_file <pssh.pssh_client.ParallelSSHClient.copy_remote_file>`  API documentation and exceptions raised.

Single host copy
-----------------

If wanting to copy a file from a single remote host and retain the original filename, can use the single host :py:class:`SSHClient <pssh.ssh_client.SSHClient>` and its :py:func:`copy_file <pssh.ssh_client.SSHClient.copy_remote_file>` directly.

.. code-block:: python

   from pssh.pssh_client import SSHClient

   client = SSHClient('localhost')
   client.copy_remote_file('remote_filename', 'local_filename')

.. seealso::

   :py:func:`SSHClient.copy_remote_file <pssh.clients.native.SSHClient.copy_remote_file>`  API documentation and exceptions raised.


Hosts filtering and overriding
*******************************

Iterators and filtering
------------------------

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
----------------------

Hosts list can be modified in place. A call to ``run_command`` will create new connections as necessary and output will only contain output for the hosts ``run_command`` executed on.

.. code-block:: python

   client = <..>

   client.hosts = ['otherhost']
   print(client.run_command('exit 0'))
   {'otherhost': exit_code=None, <..>}

Additional options for underlying SSH libraries
************************************************

Not all SSH library configuration options are used directly by ``parallel-ssh``.

Additional options can be passed on to the underlying SSH libraries used via an optional keyword argument.

Please note that the underlying SSH libraries used are subject to change and not all features are present in all SSH libraries used. Future releases will have more than one option on which SSH library to use, depending on user requirements and preference.

*New in version 1.1.*

Paramiko based clients (``pssh.clients.miko``)
-----------------------------------------------

.. note::

   When using the paramiko based clients, ``parallel-ssh`` makes use of gevent's monkey patching to enable asynchronous use of the Python standard library's network I/O as paramiko does not and cannot natively support non-blocking mode.

   Monkey patching is only done for the clients under ``pssh.clients.miko`` and the deprecated imports ``pssh.pssh_client`` and ``pssh.ssh_client``.

   Default client imports from ``pssh.clients`` do not do any monkey patching.

   Make sure that these imports come **before** any other imports in your code in this case. Otherwise, patching may not be done before the standard library is loaded which will then cause the (g)event loop to be blocked.

   If you are seeing messages like ``This operation would block forever``, this is the cause.

   Paramiko based clients are deprecated and will be *removed* in the ``2.0.0`` release.


GSS-API Authentication - aka Kerberos
+++++++++++++++++++++++++++++++++++++++

GSS authentication allows logins using Windows LDAP configured user accounts via Kerberos on Linux.

.. code-block:: python

   from pssh.clients.miko import ParallelSSHClient
   
   client = ParallelSSHClient(hosts)

   client.run_command('id', gss_auth=True, gss_kex=True, gss_host='my_gss_host')

In this example, ``gss_auth``, ``gss_kex`` and ``gss_host`` are keyword arguments passed on to `paramiko.client.SSHClient.connect <http://paramiko-docs.readthedocs.io/en/stable/api/client.html#paramiko.client.SSHClient.connect>`_ to instruct the client to enable GSS-API authentication and key exchange with the provided GSS host.

.. note::

   The GSS-API features of Paramiko require that the ``python-gssapi`` package be installed manually - it is optional and not installed by any *extras* option of Paramiko.

   ``pip install python-gssapi``

Compression
++++++++++++

Any other options not directly referenced by ``run_command`` can be passed on to `paramiko.client.SSHClient.connect <http://paramiko-docs.readthedocs.io/en/stable/api/client.html#paramiko.client.SSHClient.connect>`_, for example the ``compress`` option.

.. code-block:: python

   client = ParallelSSHClient(hosts)

   client.run_command('id', compress=True)
