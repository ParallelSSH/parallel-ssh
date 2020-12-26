===========================
Parallel-SSH Documentation
===========================

.. image:: https://img.shields.io/badge/License-LGPL%20v2.1-blue.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: License
.. image:: https://img.shields.io/pypi/v/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
  :alt: Latest Version
.. image:: https://circleci.com/gh/ParallelSSH/parallel-ssh/tree/master.svg?style=svg
  :target: https://circleci.com/gh/ParallelSSH/parallel-ssh
.. image:: https://codecov.io/gh/ParallelSSH/parallel-ssh/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/ParallelSSH/parallel-ssh
.. image:: https://img.shields.io/pypi/wheel/parallel-ssh.svg
  :target: https://pypi.python.org/pypi/parallel-ssh
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: http://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation

``parallel-ssh`` is a non-blocking parallel SSH client library.

It provides clients based on C libraries with an easy to use Python API providing native code levels of performance and stability.


In a nutshell
**************

Client will attempt to use all available keys under ``~/.ssh`` as well as any keys in an SSH agent, if one is available.

.. code-block:: python

   from pssh.clients import ParallelSSHClient

   client = ParallelSSHClient(['localhost', 'localhost'])
   output = client.run_command('uname')
   for host_out in output:
       for line in host_out.stdout:
           print(line)
       exit_code = host_out.exit_code

:Output:
   .. code-block:: python

      <Uname output>
      <Uname output>


Single Host Client
******************

Single host client is also available with similar API.

.. code-block:: python

   from pssh.clients import SSHClient

   client = SSHClient('localhost')
   host_out = client.run_command('uname')
   for line in host_out.stdout:
       print(line)
   exit_code = host_out.exit_code

:Output:
   .. code-block:: python

      <Uname output>


.. toctree::
   :maxdepth: 2

   introduction
   installation
   quickstart
   advanced
   api
   clients
   Changelog
   api_upgrade_2_0


Indices and tables
==================

* :ref:`genindex`
