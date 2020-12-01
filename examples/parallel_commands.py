from pssh.clients import ParallelSSHClient
import datetime

output = []
host = 'localhost'
hosts = [host, host]
client = ParallelSSHClient(hosts)

# Run 10 five second sleeps
cmds = ['sleep 5; uname' for _ in range(10)]
start = datetime.datetime.now()
for cmd in cmds:
    output.append(client.run_command(cmd, stop_on_errors=False, return_list=True))
end = datetime.datetime.now()
print("Started %s 'sleep 5' commands on %s host(s) in %s" % (
    len(cmds), len(hosts), end-start,))
start = datetime.datetime.now()
for _output in output:
    client.join(_output)
    for host_out in _output:
        for line in host_out.stdout:
            print(line)
        for line in host_out.stderr:
            print(line)
        print(f"Exit code: {host_out.exit_code}")
end = datetime.datetime.now()
print("All commands finished in %s" % (end-start,))
