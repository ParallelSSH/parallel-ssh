.. Parallel-SSH documentation master file, created by
   sphinx-quickstart on Mon Mar 10 17:08:38 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Parallel-SSH's documentation
============================

.. toctree::
   :hidden:
   
   front_page

In a nutshell::

  client = ParallelSSHClient(['localhost'])
  output = client.run_command('whoami')
  for line in output['localhost'].stdout:
      print(line)

Output::

  <your username here>

Indices and tables
==================

* :ref:`genindex`
