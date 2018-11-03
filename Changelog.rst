Change Log
============


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
