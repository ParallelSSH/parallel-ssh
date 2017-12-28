===========================
Parallel-SSH Documentation
===========================

.. image:: https://img.shields.io/badge/License-LGPL%20v2-blue.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: License
.. image:: https://img.shields.io/pypi/v/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: Latest Version
.. image:: https://travis-ci.org/ParallelSSH/parallel-ssh.svg?branch=master
  :target: https://travis-ci.org/ParallelSSH/parallel-ssh
.. image:: https://ci.appveyor.com/api/projects/status/github/parallelssh/ssh2-python?svg=true&branch=master
  :target: https://ci.appveyor.com/project/pkittenis/ssh2-python
.. image:: https://codecov.io/gh/ParallelSSH/parallel-ssh/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/ParallelSSH/parallel-ssh
.. image:: https://img.shields.io/pypi/wheel/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: http://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation

``parallel-ssh`` is a non-blocking parallel SSH client library.

It uses non-blocking asynchronous SSH sessions and is to date the only publicly available non-blocking SSH client library, as well as the only non-blocking *parallel* SSH client library available for Python.

.. toctree::
   :maxdepth: 2

   introduction
   installation
   quickstart
   ssh2
   advanced
   Changelog
   api

In a nutshell
**************

.. code-block:: python

   from __future__ import print_function

   from pssh.pssh_client import ParallelSSHClient

   client = ParallelSSHClient(['localhost'])
   output = client.run_command('whoami')
   for line in output['localhost'].stdout:
       print(line)

:Output:
   .. code-block:: python

      <your username here>

`ssh2-python` (`libssh2`) based clients
******************************************

As of version ``1.2.0``, new single host and parallel clients are available based on the ``libssh2`` C library via its ``ssh2-python`` wrapper.

They offer significantly enhanced performance and stability, at much less overhead, with a native non-blocking mode meaning *no monkey patching of the Python standard library* when using them.

To use them, import from ``pssh2_client`` or ``ssh2_client`` for the parallel and single clients respectively.

.. code-block:: python

   from __future__ import print_function

   from pssh.pssh2_client import ParallelSSHClient

   client = ParallelSSHClient(['localhost'])
   output = client.run_command('whoami')
   for line in output['localhost'].stdout:
       print(line)

The API is mostly identical to the current clients, though some features are not yet supported. See `client feature comparison <ssh2.html>`_ section for how feature support differs between the two clients.

.. note::

   From version ``2.x.x`` onwards, the ``ssh2-python`` based clients will *become the default*, replacing the current ``pssh_client.ParallelSSHClient``, with the current clients renamed.


Indices and tables
==================

* :ref:`genindex`
