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
   api
   Changelog

In a nutshell
**************

Client will attempt to use all available keys under ``~/.ssh`` as well as any keys in an SSH agent, if one is available.

.. code-block:: python

   from __future__ import print_function

   from pssh.clients import ParallelSSHClient

   client = ParallelSSHClient(['localhost'])
   output = client.run_command('whoami')
   for line in output['localhost'].stdout:
       print(line)

:Output:
   .. code-block:: python

      <your username here>

.. note::

   There is also a now deprecated paramiko based client available under ``pssh.clients.miko`` that has much the same API. It supports some features not currently supported by the native client - see `feature comparison <ssh2.html>`_.

   From version ``2.x.x`` onwards, the clients under ``pssh.clients.miko`` will be an optional ``extras`` install.


Indices and tables
==================

* :ref:`genindex`
