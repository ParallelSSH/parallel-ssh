Upgrading to API 2.0
######################

Here can be found code examples for the ``1.x`` API and how they can be migrated to the new ``2.x`` API.

Code that was already making use of ``run_command(<..>, return_list=True`` is compatible with the ``2.x`` API - ``return_list=True`` parameter may now be removed.

Parallel Client Run Command
***************************


1.x code
=========

.. code-block:: python

   client = ParallelSSHClient(..)

   output = client.run_command(<cmd>)
   for host, host_out in output.values():
       <..>


2.x code
=========

.. code-block:: python

   client = ParallelSSHClient(..)

   output = client.run_command(<cmd>)
   for host_out in output:
       host = host_out.host
       <..>

Parallel Client Get last output
*******************************


1.x code
=========

.. code-block:: python

   client = ParallelSSHClient(..)

   output = client.get_last_output()
   for host, host_out in output.values():
       <..>


2.x code
=========

.. code-block:: python

   client = ParallelSSHClient(..)

   output = client.get_last_output()
   for host_out in output:
       host = host_out.host
       <..>


Single Client Run Command
*************************

1.x code
=========

.. code-block:: python

   client = SSHClient(..)

   channel, host, stdout, stderr, stdin = client.run_command(<cmd>)
   for line in stdout:
       <..>
   exit_code = client.get_exit_status(channel)


2.x code
=========

.. code-block:: python

   client = SSHClient(..)

   host_out = client.run_command(<cmd>)
   for line in host_out.stdout:
       <..>
   exit_code = host_out.exit_code
