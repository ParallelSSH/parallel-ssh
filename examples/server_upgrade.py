#!/usr/bin/python
#Midhlaj VS : midhlaj.vs@gmail.com

from pprint import pprint
from pssh.pssh_client import ParallelSSHClient
from pssh.utils import enable_host_logger

""" Connect to the servers listed in the file server_list.txt and execute the commands on commands.txt
sequentially on each host """

class upgrade:
     
  # Generate two lists using the text files provided, server_list.txt and commands.txt. Each line in 
  # the files will be added as an element in the respective list. 
  # -- Servers IPs/hostnames should be listed in server_list.txt file as one IP/hostname per each line. 
  # -- Commands to be executed should be added in the same manner to the file commands.txt, one per line. 
  
  def __init__(self):

     self.hosts = open("server_list.txt").readlines()
     self.commands = open("commands.txt").readlines()
  
  #Generate connections and execute command on all hosts
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
