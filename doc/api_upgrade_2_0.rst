Upgrading to API 2.0
######################


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
