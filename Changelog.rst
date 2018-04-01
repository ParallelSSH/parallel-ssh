Change Log
============

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
