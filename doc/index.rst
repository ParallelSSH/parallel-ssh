.. Parallel-SSH documentation master file, created by
   sphinx-quickstart on Mon Mar 10 17:08:38 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

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
.. image:: https://coveralls.io/repos/ParallelSSH/parallel-ssh/badge.png?branch=master
  :target: https://coveralls.io/r/ParallelSSH/parallel-ssh?branch=master
.. image:: https://readthedocs.org/projects/parallel-ssh/badge/?version=latest
  :target: http://parallel-ssh.readthedocs.org/en/latest/
  :alt: Latest documentation


``Parallel-SSH`` is a parallel SSH client library. It uses asynchronous SSH connections and is, to date, the only publicly available asynchronous SSH client library for Python, as well as the only asynchronous *parallel* SSH client library available for Python.

.. toctree::
   :maxdepth: 2

   introduction
   installation
   quickstart
   advanced
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

Indices and tables
==================

* :ref:`genindex`
