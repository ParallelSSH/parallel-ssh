from pssh import ParallelSSHClient
import datetime

output = []
host = '192.168.1.2'
hosts = [host]
client = ParallelSSHClient(hosts)
import ipdb; ipdb.set_trace()

# Run 10 five second sleeps
cmds = ['sleep 5' for _ in xrange(10)]
start = datetime.datetime.now()
for cmd in cmds:
    output.append(client.run_command(cmd, stop_on_errors=False))
end = datetime.datetime.now()
print("Started %s commands on %s host(s) in %s" % (
    len(cmds), len(hosts), end-start,))
start = datetime.datetime.now()
for _output in output:
    client.join(_output)
    print(_output)
end = datetime.datetime.now()
print("All commands finished in %s" % (end-start,))
