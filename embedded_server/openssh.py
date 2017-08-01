import os
import socket

from gevent.subprocess import Popen
from gevent import sleep


SERVER_KEY = os.path.sep.join([os.path.dirname(__file__), 'rsa.key'])
SSHD_CONFIG = os.path.sep.join([os.path.dirname(__file__), 'sshd_config'])

class OpenSSHServer(object):

    def __init__(self, port=2222):
        self.port = port
        self.server_proc = None

    def start_server(self):
        cmd = ['/usr/sbin/sshd', '-D', '-p', str(self.port),
               '-h', SERVER_KEY, '-f', SSHD_CONFIG]
        server = Popen(cmd)
        self.server_proc = server
        self._wait_for_port()

    def _wait_for_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while sock.connect_ex(('127.0.0.1', self.port)) != 0:
            sleep(.1)
        sleep(.1)
        del sock

    def stop(self):
        if self.server_proc is not None and self.server_proc.returncode is None:
            self.server_proc.terminate()
            self.server_proc.wait()

    def __del__(self):
        self.stop()
