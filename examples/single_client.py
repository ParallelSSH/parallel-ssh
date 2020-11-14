from pssh.clients import SSHClient
from datetime import datetime


host = 'localhost'
cmds = ['echo first command',
        'echo second command',
        'sleep 1; echo third command took one second',
        ]
client = SSHClient(host)

start = datetime.now()
for cmd in cmds:
    out = client.run_command(cmd)
    for line in out.stdout:
        print(line)
end = datetime.now()
print("Took %s seconds" % (end - start).total_seconds())
