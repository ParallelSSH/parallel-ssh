Change Log
============

2.9.0
+++++

Changes
--------

* ``pssh.exceptions.ConnectionError`` is now the same as built-in ``ConnectionError`` and deprecated - to be removed.
* Clients now continue connecting with all addresses in DNS list. In the case where an address refuses connection,
  other available addresses are attempted without delay.
  For example where a host resolves to both IPv4 and v6 addresses while only one address is
  accepting connections, or multiple v4/v6 addresses where only some are accepting connections.
* Connection actively refused error is no longer subject to retries.

2.8.0
+++++

Changes
--------

* All clients now support private key data as bytes in ``pkey`` parameter for authentication from in-memory private key
  data - #317. See `documentation <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#in-memory-private-keys>`_
  for examples.
* Parallel clients now read a provided private key path only once and use in-memory data for authentication to avoid
  reading same file multiple times, if a path is provided.


2.7.1
+++++

Fixes
------

* ``copy_file`` performance would be abnormally low when copying plain text files - 100x performance increase. Binary
  file copying performance has also increased.


2.7.0
+++++

Changes
-------

* All clients now support IPv6 addresses for both DNS and IP entries in host list.
* Added ``ipv6_only`` flag to ``ParallelSSHClient`` and ``SSHClient`` for choosing only IPv6 addresses when both v4 and
  v6 are available.
* Removed Python 2 from binary wheel compatibility as it is no longer supported and not guaranteed to work.
* Host name is now an argument for all exceptions raised by single clients.

Fixes
-----

* ``HostOutput`` would have empty host on some exceptions when ``stop_on_errors`` is ``False`` - #297
* Race condition when forcefully closing channel via ``SSHClient.close_channel`` while channel data was left unread.

2.6.0
+++++

Changes
-------

* ``user`` keyword argument no longer required on Windows - exception is raised if user cannot be identified.
* Removed deprecated since ``2.0.0`` functions and parameters.

Fixes
-----

* ``copy_remote_file`` with recurse enabled would not use a provided encoding for sub-directories - #284
* Reconnecting to the same proxy host when proxy is configured would sometimes cause segfauls - ##304


2.5.4
+++++

Fixes
------

* Password authentication via ``pssh.clients.ssh`` would not work - #276


2.5.3
+++++

Fixes
-----

* Sending files via ``scp_send`` or ``sftp_put`` with timeout set could timeout unexpectedly on opening remote file - #271.


2.5.2
+++++

Fixes
-----

* Agent authentication would not work for the libssh clients under ``pssh.clients.ssh`` - #267.
* Password authentication would be attempted if all other methods failed even when no password was provided.
* Gevent minimum version was too low - #269.

2.5.1
+++++

Fixes
-----

* Successful identity file authentication would raise error - #264.

2.5.0
+++++

Changes
-------

* Python 2 no longer supported.
* Updated class arguments, refactor for ``pssh.clients.native.tunnel``.

Fixes
-----

* Closed clients with proxy host enabled would not shutdown their proxy servers.
* Clients with proxy host enabled would not disconnect the proxy client on ``.disconnect`` being called.
* Default identity files would not be used when private key was not specified - #222.
* ``ParallelSSHClient(<..>, identity_auth=False`` would not be honoured.


2.4.0
+++++

Changes
-------

* Added interactive shell support to single and parallel clients - see `documentation <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#interactive-shells>`_.
* Added ``pssh.utils.enable_debug_logger`` function.
* ``ParallelSSHClient`` timeout parameter is now also applied to *starting* remote commands via ``run_command``.
* ``HostOutput.stdin`` now handles EAGAIN automatically when writing - #165.
* Assigning to ``ParallelSSHClient.hosts`` cleans up clients of hosts no longer in host list - #220.

Fixes
-----

* ``SSHClient`` with proxy enabled could not be used without setting port - #248
* Encoding would not be applied to command string on ``run_command`` and interactive shells, `utf-8` used instead - #174.


2.3.2
+++++

Fixes
-----

* Client output implementation Python 2 support.


2.3.1
+++++

Changes
-------

* ``SSHClient.read_output`` and ``read_stderr`` now take buffer to read from as argument instead of channel.
* ``SSHClient.wait_finished`` now takes ``HostOutput`` argument instead of channel.

Fixes
-----

* Output for multiple commands on one host run at the same time would be lost.


2.3.0
+++++

Changes
-------

* ``SSHClient`` now starts buffering output from remote host, both standard output and standard error, when a command is run.
* ``SSHClient.read_output``, ``SSHClient.read_stderr`` and iterating on stdout/stderr from ``HostOutput`` now read from the internal buffer rather than the SSH channel directly.
* ``ParallelSSHClient.join`` no longer requires ``consume_output`` to be set in order to get exit codes without first reading output.
* ``ParallelSSHClient.join`` with timeout no longer consumes output by default. It is now possible to use ``join`` with a timeout and capture output after ``join`` completes.
* ``ParallelSSHClient.reset_output_generators`` is now a no-op and no longer required to be called after timeouts.
* ``HostOutput.stdout`` and ``stderr`` are now dynamic properties.
* Added ``HostOutput.read_timeout`` attribute. Can be used to see what read timeout was when ``run_command`` was called and to change timeout when next reading from ``HostOutput.stdout`` and ``stderr``.
* Added ``HostOutput.encoding`` attribute for encoding used when ``run_command`` was called. Encoding can now be changed for when next reading output.
* ``ParallelSSHClient.join`` with timeout no longer affects ``stdout`` or ``stderr`` read timeout set when ``run_command`` was called.
* LibSSH clients under ``pssh.clients.ssh`` now allow output to be read as it becomes available without waiting for remote command to finish first.
* Reading from output behaviour is now consistent across all client types - parallel and single clients under both ``pssh.clients.native`` and ``pssh.clients.ssh``.
* ``ParallelSSHClient.join`` can now be called without arguments and defaults to last ran commands.
* ``ParallelSSHClient.finished`` can now be called without arguments and defaults to last ran commands.


This is now possible:

.. code-block:: python

   output = client.run_command(<..>)
   client.join(output)
   assert output[0].exit_code is not None

As is this:

.. code-block:: python

   client.run_command(<..>, read_timeout=1)
   client.join(output, timeout=1)
   for line in output[0].stdout:
       print(line)

Output can be read after and has separate timeout from join.

See `documentation for more examples on use of timeouts <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#partial-output>`_.


2.2.0
+++++

Changes
-------

* New single host tunneling, SSH proxy, implementation for increased performance.
* Native ``SSHClient`` now accepts ``proxy_host``, ``proxy_port`` and associated parameters - see `API documentation <https://parallel-ssh.readthedocs.io/en/latest/config.html>`_.
* Proxy configuration can now be provided via ``HostConfig``.
* Added ``ParallelSSHClient.connect_auth`` function for connecting and authenticating to hosts in parallel.


2.1.0
+++++

Changes
-------

* Added certificate authentication support for the ``pssh.clients.ssh`` clients.

2.0.0
+++++

Changes
--------

See `Upgrading to API 2.0 <https://parallel-ssh.readthedocs.io/en/latest/api_upgrade_2_0.html>`_ for examples of code that will need updating.

* Removed paramiko clients and dependency.
* ``ParallelSSHClient.run_command`` now always returns a list of ``HostOutput`` - ``return_list`` argument is a no-op and may be removed.
* ``ParallelSSHClient.get_last_output`` now always returns a list of ``HostOutput``.
* ``SSHClient.run_command`` now returns ``HostOutput``.
* Removed deprecated since `1.0.0` ``HostOutput`` dictionary attributes.
* Removed deprecated since `1.0.0` imports and modules.
* Removed paramiko based ``load_private_key`` and ``read_openssh_config`` functions from ``pssh.utils``.
* Removed paramiko based ``pssh.tunnel``.
* Removed paramiko based ``pssh.agent``.
* Removed deprecated ``ParallelSSHClient.get_output`` function.
* Removed deprecated ``ParallelSSHClient.get_exit_code`` and ``get_exit_codes`` functions.
* Removed deprecated ``ParallelSSHClient`` ``host_config`` dictionary implementation - now list of ``HostConfig``.
* Removed ``HostOutput.cmd`` attribute.
* Removed ``ParallelSSHClient.host_clients`` attribute.
* Made ``ParallelSSHClient(timeout=<seconds>)`` a global timeout setting for all operations.
* Removed ``run_command(greenlet_timeout=<..>)`` argument - now uses global timeout setting.
* Renamed ``run_command`` ``timeout`` to ``read_timeout=<seconds>)`` for setting output read timeout individually - defaults to global timeout setting.
* Removed ``pssh.native`` package and native code.
* ``ParallelSSHClient.scp_send`` now supports ``copy_args`` keyword argument for providing per-host file name arguments like rest of ``scp_*`` and ``copy_*`` functionality.
* Changed exception names to end in ``Error`` from ``Exception`` - backwards compatible.
* ``UnknownHostException``, ``AuthenticationException``, ``ConnectionErrorException``, ``SSHException`` no longer available as imports ``from pssh`` - use ``from pssh.exceptions``.


Fixes
-----

* Removed now unnecessary locking around SSHClient initialisation so it can be parallelised - #219.
* ``ParallelSSHClient.join`` with encoding would not pass on encoding when reading from output buffers - #214.
* Clients could raise ``Timeout`` early when timeout settings were used with many hosts.


Packaging
---------

* Package architecture has changed to ``none-any``.


1.13.0
++++++

Changes
--------

* Added ``pssh.config.HostConfig`` for providing per-host configuration. Replaces dictionary ``host_config`` which is now deprecated. See `per-host configuration <https://parallel-ssh.readthedocs.io/en/latest/advanced.html#per-host-configuration>`_ documentation.
* ``ParallelSSHClient.scp_send`` and ``scp_recv`` with directory target path will now copy source file to directory keeping existing name instead of failing when recurse is off - #183.
* ``pssh.clients.ssh.SSHClient`` ``wait_finished`` timeout is now separate from ``SSHClient(timeout=<timeout>)`` session timeout.
* ``ParallelSSHClient.join`` with timeout now has finished and unfinished commands as ``Timeout`` exception arguments for use by client code.

Fixes
------

* ``ParallelSSHClient.copy_file`` with recurse enabled and absolute destination path would create empty directory in home directory of user - #197.
* ``ParallelSSHClient.copy_file`` and ``scp_recv`` with recurse enabled would not create remote directories when copying empty local directories.
* ``ParallelSSHClient.scp_send`` would require SFTP when recurse is off and remote destination path contains directory - #157.
* ``ParallelSSHClient.scp_recv`` could block infinitely on large - 200-300MB or more - files.
* ``SSHClient.wait_finished`` would not apply timeout value given.


1.12.1
++++++

Fixes
------

* Reading from output streams with timeout via `run_command(<..>, timeout=<timeout>)` would raise timeout early when trying to read from a stream with no data written to it while other streams have pending data - #180.


1.12.0
++++++

Changes
--------

* Added `ssh-python` (`libssh <https://libssh.org>`_) based native client with `run_command` implementation.
* ``ParallelSSHClient.join`` with timeout no longer consumes output by default to allow reading of output after timeout.

Fixes
------

* ``ParallelSSHClient.join`` with timeout would raise ``Timeout`` before value given when client was busy with other commands.

.. note::

   ``ssh-python`` client at `pssh.clients.ssh.ParallelSSHClient` is available for testing. Please report any issues.

   To use:

   .. code-block:: python

      from pssh.clients.ssh import ParallelSSHClient

This release adds (yet another) client, this one based on `ssh-python <https://github.com/ParallelSSH/ssh-python>`_ (`libssh <https://libssh.org>`_). Key features of this client are more supported authentication methods compared to `ssh2-python`.

Future releases will also enable certificate authentication for the ssh-python client.

Please migrate to one of the two native clients if have not already as paramiko is very quickly accumulating yet more bugs and the `2.0.0` release which removes it is imminent.

Users that require paramiko for any reason can pin their parallel-ssh versions to `parallel-ssh<2.0.0`.


1.11.2
++++++

Fixes
------

* `ParallelSSHClient` going out of scope would cause new client sessions to fail if `client.join` was not called prior - #200


1.11.0
++++++

Changes
-------

* Moved polling to gevent.select.poll to increase performance and better handle high number of sockets - #189
* ``HostOutput.exit_code`` is now a dynamic property returning either ``None`` when exit code not ready or the exit code as reported by channel. ``ParallelSSHClient.get_exit_codes`` is now a no-op and scheduled to be removed.
* Native client exit codes are now more explicit and return ``None`` if no exit code is ready. Would previously return ``0`` by default.


Packaging
---------

* Removed OSX Python 3.6 and 3.7 wheels. OSX wheels for brew python, currently 3.8, on OSX 10.14 and 10.15 are provided.

Fixes
------

* Native client would fail on opening sockets with large file descriptor values - #189


1.10.0
+++++++

Changes
--------

* Added ``return_list`` optional argument to ``run_command`` to return list of ``HostOutput`` objects as output rather than dictionary - defaults to ``False``. List output will become default starting from ``2.0.0``.
* Updated native clients for new version of ``ssh2-python``.
* Manylinux 2010 wheels.


Fixes
------

* Sockets would not be closed on client going out of scope - #175
* Calling ``join()`` would reset encoding set on ``run_command`` - #159


1.9.1
++++++

Fixes
-----

* Native client SCP and SFTP uploads would not handle partial writes from waiting on socket correctly.
* Native client ``copy_file`` SFTP upload would get stuck repeating same writes until killed when copying multi-MB files from Windows clients - #148
* Native client ``scp_send`` would not correctly preserve file mask of local file on the remote.
* Native client tunnel, used for proxy implementation, would not handle partial writes from waiting on socket correctly.


1.9.0
++++++

Changes
--------

* Removed libssh2 native library dependency in favour of bundled ``ssh2-python`` libssh2 library.
* Changed native client forward agent default behaviour to off due to incompatibility with certain SSH server implementations.
* Added keep-alive functionality to native client - defaults to ``60`` seconds. ``ParallelSSHClient(<..>, keepalive_seconds=<interval>)`` to configure interval. Set to ``0`` to disable.
* Added ``~/.ssh/id_ecdsa`` default identity location to native client.


1.8.2
++++++

Fixes
------

* Native parallel client ``forward_ssh_agent`` flag would not be applied correctly.

1.8.1
++++++

Fixes
------

* Native client socket timeout setting would be longer than expected - #133

Packaging
---------

* Added Windows 3.7 wheels

1.8.0
++++++

Changes
--------

* Native client no longer requires public key file for authentication.
* Native clients raise ``pssh.exceptions.PKeyFileError`` on object initialisation if provided private key file paths cannot be found.
* Native clients expand user directory (``~/<path>``) on provided private key paths.
* Parallel clients raise ``TypeError`` when provided ``hosts`` is a string instead of list or other iterable.

1.7.0
++++++

Changes
--------

* Better tunneling implementation for native clients that supports multiple tunnels over single SSH connection for connecting multiple hosts through single proxy.
* Added ``greenlet_timeout`` setting to native client ``run_command`` to pass on to getting greenlet result to allow for greenlets to timeout.
* Native client raises specific exceptions on non-authentication errors connecting to host instead of generic ``SessionError``.


Fixes
------

* Native client tunneling would not work correctly - #123.
* ``timeout`` setting was not applied to native client sockets.
* Native client would have ``SessionError`` instead of ``Timeout`` exceptions on timeout errors connecting to hosts.

1.6.3
++++++

Changes
--------

* Re-generated C code with latest Cython release.

Fixes
------

* ``ssh2-python`` >= 0.14.0 support.

1.6.2
++++++

Fixes
------

* Native client proxy initialisation failures were not caught by ``stop_on_errors=False`` - #121.

1.6.1
+++++++

Fixes
-------

* Host would always be `127.0.0.1` when using ``proxy_host`` on native client - #120.

1.6.0
++++++

Changes
--------

* Added ``scp_send`` and ``scp_recv`` functions to native clients for sending and receiving files via SCP respectively.
* Refactoring - clients moved to their own sub-package - ``pssh.clients`` - with backwards compatibility for imports from ``pssh.pssh_client`` and ``pssh.pssh2_client``.
* Show underlying exception from native client library when raising ``parallel-ssh`` exceptions.
* ``host`` parameter added to all exceptions raised by parallel clients - #116
* Deprecation warning for client imports.
* Deprecation warning for default client changing from paramiko to native client as of ``2.0.0``.
* Upgrade embedded ``libssh2`` in binary wheels to latest version plus enhancements.
* Adds support for ECDSA host keys for native client.
* Adds support for SHA-256 host key fingerprints for native client.
* Added SSH agent forwarding to native client, defaults to on as per paramiko client - ``forward_ssh_agent`` keyword parameter.
* Windows wheels switched to OpenSSL back end for native client.
* Windows wheels include zlib and have compression enabled for native client.
* Added OSX 10.13 wheel build.

Fixes
------

* Windows native client could not connect to newer SSH servers - thanks Pavel.

Note - libssh2 changes apply to binary wheels only. For building from source, `see documentation <http://parallel-ssh.readthedocs.io/en/latest/installation.html#building-from-source>`_.

1.5.5
++++++

Fixes
------

* Use of ``sudo`` in native client incorrectly required escaping of command.

1.5.4
++++++

Changes
--------

* Compatibility with ``ssh2-python`` >= ``0.11.0``.

1.5.2
++++++

Changes
--------

* Output generators automatically restarted on call to ``join`` so output can resume on any timeouts.

1.5.1
++++++

Fixes
--------

* Output ``pssh.exceptions.Timeout`` exception raising was not enabled.

1.5.0
++++++

Changes
---------

* ``ParallelSSH2Client.join`` with timeout now consumes output to ensure command completion status is accurate.
* Output reading now raises ``pssh.exceptions.Timeout`` exception when timeout is requested and reached with command still running.

Fixes
------

* ``ParallelSSH2Client.join`` would always raise ``Timeout`` when output has not been consumed even if command has finished - #104.

1.4.0
++++++

Changes
----------

* ``ParallelSSH2Client.join`` now raises ``pssh.exceptions.Timeout`` exception when timeout is requested and reached with command still running.


Fixes
--------

* ``ParallelSSH2Client.join`` timeout duration was incorrectly for per-host rather than total.
* SFTP read flags were not fully portable.

1.3.2
++++++

Fixes
-------

* Binary wheels would have bad version info and require `git` for installation.

1.3.1
++++++

Changes
--------

* Added ``timeout`` optional parameter to ``join`` and ``run_command``, for reading output, on native clients.

Fixes
------

* From source builds when Cython is installed with recent versions of ``ssh2-python``.

1.3.0
++++++

Changes
---------

* Native clients proxy implementation
* Native clients connection and authentication retry mechanism

Proxy/tunnelling implementation is experimental - please report any issues.

1.2.1
++++++

Fixes
------

* PyPy builds

1.2.0
++++++

Changes
---------

* New ``ssh2-python`` (``libssh2``) native library based clients
* Added ``retry_delay`` keyword parameter to parallel clients
* Added ``get_last_output`` function for retrieving output of last executed commands
* Added ``cmds`` attribute to parallel clients for last executed commands

Fixes
--------

* Remote path for SFTP operations was created incorrectly on Windows - #88 - thanks @moscoquera
* Parallel client key error when openssh config with a host name override was used - #93
* Clean up after paramiko clients

1.1.1
++++++

Changes
---------

* Accept Paramiko version ``2`` but < ``2.2`` (it's buggy).

1.1.0
+++++++

Changes
---------

* Allow passing on of additional keyword arguments to underlying SSH library via ``run_command`` - #85

1.0.0
+++++++

Changes from `0.9x` series API
--------------------------------

- `ParallelSSHClient.join` no longer consumes output buffers
- Command output is now a dictionary of host name -> `host output object <http://parallel-ssh.readthedocs.io/en/latest/output.html>`_ with `stdout` and et al attributes. Host output supports dictionary-like item lookup for backwards compatibility. No code changes are needed to output use though documentation will from now on refer to the new attribute style output. Dictionary-like item access is deprecated and will be removed in future major release, like `2.x`.
- Made output encoding configurable via keyword argument on `run_command` and `get_output`
- `pssh.output.HostOutput` class added to hold host output
- Added `copy_remote_file` function for copying remote files to local ones in parallel
- Deprecated since `0.70.0` `ParallelSSHClient` API endpoints removed
- Removed setuptools >= 28.0.0 dependency for better compatibility with existing installations. Pip version dependency remains for Py 2.6 compatibility with gevent - documented on project's readme
- Documented `use_pty` parameter of run_command
- `SSHClient` `read_output_buffer` is now public function and has gained callback capability
- If using the single `SSHClient` directly, `read_output_buffer` should now be used to read output buffers - this is not needed for `ParallelSSHClient`
- `run_command` now uses named positional and keyword arguments
