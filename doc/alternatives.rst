Comparison With Alternatives
*****************************

There are not many alternatives for SSH libraries in Python. Of the few that do exist, here is how they compare with ``parallel-ssh``.

As always, it is best to use a tool that is suited to the task at hand. ``parallel-ssh`` is a library for programmatic and non-interactive use. If requirements do not match what it provides then it best not be used. Same applies for the tools described below.

Paramiko
________

The default SSH client library in ``parallel-ssh`` <=``1.6.x`` series.

Pure Python code, while having native extensions as dependencies, with poor performance and numerous bugs compared to both OpenSSH binaries and the ``libssh2`` based native clients in ``parallel-ssh`` ``1.2.x`` and above. Recent versions have regressed in performance and have `blocker issues <https://github.com/ParallelSSH/parallel-ssh/issues/83>`_.

It does not support non-blocking mode, so to make it non-blocking monkey patching must be used which affects all other uses of the Python standard library.

Based on its use in historical ``parallel-ssh`` releases, paramiko is very far from being mature enough to be widely used.

This is why ``parallel-ssh`` has moved away from paramiko entirely since ``2.0.0``, where it was dropped as a dependency.

asyncssh
________

Pure Python ``asyncio`` framework using client library. License (`EPL`) is not compatible with GPL, BSD or other open source licenses and `combined works cannot be distributed <https://www.eclipse.org/legal/eplfaq.php#USEINANOTHER>`_.

Therefore unsuitable for use in many projects, including ``parallel-ssh``.

Fabric
______

Port of Capistrano from Ruby to Python. Intended for command line use and is heavily systems administration oriented rather than non-interactive library. Same maintainer as Paramiko.

Uses Paramiko and suffers from the same limitations. More over, uses threads for parallelisation, while `not being thread safe <https://github.com/fabric/fabric/issues/1433>`_, and exhibits very poor performance and extremely high CPU usage even for limited number of hosts - 1 to 10 - with scaling limited to one core.

Library API is non-standard, poorly documented and with numerous issues as API use is not intended.

Ansible
_______

A configuration management and automation tool that makes use of SSH remote commands. Uses, in parts, both Paramiko and OpenSSH binaries.

Similarly to Fabric, uses threads for parallelisation and suffers from the poor scaling that this model offers.

See `The State of Python SSH Libraries <https://parallel-ssh.org/post/ssh2-python/>`_ for what to expect from scaling SSH with threads, as compared `to non-blocking I/O <https://parallel-ssh.org/post/parallel-ssh-libssh2/>`_ with ``parallel-ssh``.

Again similar to Fabric, its intended and documented use is interactive via command line rather than library API based. It may, however, be an option if Ansible is already being used for automation purposes with existing playbooks, the number of hosts is small, and when the use case is interactive via command line.

``parallel-ssh`` is, on the other hand, a suitable option for Ansible as an SSH client that would improve its parallel SSH performance significantly.

ssh2-python
___________

Bindings for ``libssh2`` C library. Used by ``parallel-ssh`` as of ``1.2.0`` and is by same author.

Does not do parallelisation out of the box but can be made parallel via Python's ``threading`` library relatively easily and as it is a wrapper to a native library that releases Python's GIL, can scale to multiple cores.

``parallel-ssh`` uses ``ssh2-python`` in its native non-blocking mode with event loop and co-operative sockets provided by ``gevent`` for an extremely high performance library without the side-effects of monkey patching - see `benchmarks <https://parallel-ssh.org/post/parallel-ssh-libssh2>`_.

In addition, ``parallel-ssh`` uses native threads to offload CPU bound tasks like authentication in order to scale to multiple cores while still remaining non-blocking for network I/O.

``pssh.clients.native.SSHClient`` is a single host natively non-blocking client for users that do not need parallel capabilities but still want a fully featured client with native code performance.

Out of all the available Python SSH libraries, ``libssh2`` and ``ssh2-python`` have been shown, see benchmarks above, to perform the best with the least resource utilisation and ironically for a native code extension the least amount of dependencies. Only ``libssh2`` C library and its dependencies which are included in binary wheels.

However, it lacks support for some SSH features present elsewhere like GSS-API and certificate authentication.

ssh-python
----------

Bindings for ``libssh`` C library. A client option in ``parallel-ssh``, same author. Similar performance to ssh2-python above.

For non-blocking use, only certain functions are supported. SCP/SFTP in particular cannot be used in non-blocking mode, nor can tunnels.

Supports more authentication options compared to ``ssh2-python`` like GSS-API (Kerberos) and certificate authentication.
