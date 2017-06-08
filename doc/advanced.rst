.. contents::


***************
Advanced Usage
***************

There are several more advanced use cases of `ParallelSSH`, such as tunneling (aka proxying) via an intermediate SSH server and per-host configuration and command substitution among others.

SSH Agent forwarding
*********************

SSH agent forwarding, what ``ssh -A`` does on the command line, is supported and enabled by default. Creating an object as ``ParallelSSHClient(hosts, forward_ssh_agent=False)`` will disable this behaviour.

Programmatic Private Keys
**************************

By default, `ParallelSSH` will use all keys in an available SSH agent and all available keys under the user's SSH directory (`~/.ssh`).

A private key can also be provided programmatically.

.. code-block:: python

  from pssh.utils import load_private_key
  from pssh import ParallelSSHClient

  client = ParallelSSHClient(hosts, pkey=load_private_key('my_key'))

Where `my_key` is a private key file in current working directory.

The helper function :py:func:`pssh.utils.load_private_key` will attempt to load all available key types and raises :mod:`pssh.exceptions.SSHException` if it cannot load the key file.

Using an available SSH agent can also be disabled programmatically.

.. code-block:: python

  client = ParallelSSHClient(hosts, pkey=load_private_key('my_key'), 
                             allow_agent=False)

Programmatic SSH Agent
***********************

It is also possible to programmatically provide an SSH agent for the client to use, instead of a system provided one. This is useful in cases where different hosts in the host list need different private keys and a system SSH agent is not available.

.. code-block:: python
   
   from pssh.agent import SSHAgent
   from pssh.utils import load_private_key
   from pssh import ParallelSSHClient

   agent = SSHAgent()
   agent.add_key(load_private_key('my_private_key_filename'))
   agent.add_key(load_private_key('my_other_private_key_filename'))
   hosts = ['my_host', 'my_other_host']

   client = ParallelSSHClient(hosts, agent=agent)
   client.run_command(<..>)

Supplying an agent object programmatically implies that a system SSH agent will *not* be used if available.


Tunneling
**********

This is used in cases where the client does not have direct access to the target host and has to authenticate via an intermediary, also called a bastion host, commonly used for additional security as only the bastion host needs to have access to the target host.

ParallelSSHClient       ------>        SSH Proxy server         -------->         SSH target host

Proxy server can be configured as follows in the simplest case::

  hosts = [<..>]
  client = ParallelSSHClient(hosts, proxy_host=bastion)
  
Configuration for the proxy host's user name, port, password and private key can also be provided, separete from target host user name.

.. code-block:: python
   
   from pssh.utils import load_private_key
   
   hosts = [<..>]
   client = ParallelSSHClient(hosts, user='target_host_user', 
                              proxy_host=bastion, proxy_user='my_proxy_user',
 			      proxy_port=2222, 
 			      proxy_pkey=load_private_key('proxy.key'))

Where `proxy.key` is a filename containing private key to use for proxy host authentication.

Per-Host Configuration
***********************

Sometimes, different hosts require different configuration like user names and passwords, ports and private keys. Capability is provided to supply per host configuration for such cases.

.. code-block:: python

   from pssh.utils import load_private_key

   host_config = {'host1' : {'user': 'user1', 'password': 'pass',
                             'port': 2222,
                             'private_key': load_private_key(
                                 'my_key.pem')},
                  'host2' : {'user': 'user2', 'password': 'pass',
		             'port': 2223,
			     'private_key': load_private_key(
			         open('my_other_key.pem'))},
		 }
   hosts = host_config.keys()

   client = ParallelSSHClient(hosts, host_config=host_config)
   client.run_command('uname')
   <..>

In the above example, `host1` will use user name `user1` and private key from `my_key.pem` and `host2` will use user name `user2` and private key from `my_other_key.pem`.

Per-Host Command substitution
******************************

For cases where different commands should be run each host, or the same command with different arguments, functionality exists to provide per-host command arguments for substitution.

The `host_args` keyword parameter to `run_command` can be used to provide arguments to use to format the command string.

Number of `host_args` items should be at least as many as number of hosts.

Any Python string format specification characters may be used in command string.


In the following example, first host in hosts list will use cmd `host1_cmd` second host `host2_cmd` and so on

.. code-block:: python
   
   output = client.run_command('%s', host_args=('host1_cmd',
                                                'host2_cmd',
						'host3_cmd',))

Command can also have multiple arguments to be substituted.

.. code-block:: python

   output = client.run_command('%s %s',
   host_args=(('host1_cmd1', 'host1_cmd2'),
              ('host2_cmd1', 'host2_cmd2'),
	      ('host3_cmd1', 'host3_cmd2'),))

A list of dictionaries can also be used as `host_args` for named argument substitution.

In the following example, first host in host list will use cmd `host-index-0`, second host `host-index-1` and so on.

.. code-block:: python

   host_args=[{'cmd': 'host-index-%s' % (i,))
              for i in range(len(client.hosts))]
   output = client.run_command('%(cmd)s', host_args=host_args)
