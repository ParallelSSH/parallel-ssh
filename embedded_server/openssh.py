import os

from gevent.subprocess import Popen


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

    def stop(self):
        if self.server_proc is not None:
            self.server_proc.terminate()
            self.server_proc.communicate()

    def __del__(self):
        self.stop()
