"""
Show backreferences of out of scope client objects, to check for cyclical references.
"""

import gc
import objgraph
import sys

from pssh.clients import SSHClient
from pssh.clients.ssh import SSHClient as LibSSHClient

host = 'localhost'


def run():
    client = SSHClient(host, allow_agent=False)
    out = client.run_command('echo me')
    for line in out.stdout:
        print(line)


def run_libssh():
    client = LibSSHClient(host, allow_agent=False)
    out = client.run_command('echo me')
    for line in out.stdout:
        print(line)


if __name__ == "__main__":
    type_name = "SSHClient"
    # type_name = "LibSSHClient"
    run()
    # run_libssh()
    gc.collect()
    objs = objgraph.by_type(type_name)
    if not objs:
        sys.stdout.write("No back references\n")
        sys.exit(0)
    objgraph.show_backrefs(objs[0], filename="chain.png")
