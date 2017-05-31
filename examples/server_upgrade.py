#!/usr/bin/python
#Midhlaj VS : midhlaj.vs@gmail.com

from pprint import pprint
from pssh.pssh_client import ParallelSSHClient
from pssh.utils import enable_host_logger

class upgrade:

  def __init__(self):

     self.hosts = open("hypervisors_kvm.txt").readlines()
     self.commands = open("commands.txt").readlines()

  def run_command(self, hosts, command):

    client = ParallelSSHClient(hosts,user='root')
    output = client.run_command(command)
    client.join(output, consume_output=False)

    for host in output:
       stdout = list(output[host].stdout)
       print ("Host :  %s  ---  Command : \"%s\" : '\n\n' %s '\n'"  % (host.rstrip('\n'), command.rstrip('\n'), '\n'.join(stdout,)))

if __name__ == "__main__":
    x = upgrade()
    for command in x.commands:
         x.run_command(x.hosts, command)
