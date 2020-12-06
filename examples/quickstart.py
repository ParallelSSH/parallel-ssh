from pssh.clients import ParallelSSHClient, SSHClient


hosts = ['localhost']
cmd = 'uname'

client = ParallelSSHClient(hosts)
output = client.run_command(cmd)

for host_out in output:
    for line in host_out.stdout:
        print(line)
print("Host %s: exit code %s" % (host_out.host, host_out.exit_code))
