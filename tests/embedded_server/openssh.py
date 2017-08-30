# This file is part of paralle-ssh.
# Copyright (C) 2014-2017 Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import os
import socket
from subprocess import Popen
from time import sleep
from sys import version_info

from jinja2 import Template


DIR_NAME = os.path.dirname(__file__)
SERVER_KEY = os.path.abspath(os.path.sep.join([DIR_NAME, 'rsa.key']))
SSHD_CONFIG_TMPL = os.path.abspath(os.path.sep.join(
    [DIR_NAME, 'sshd_config.tmpl']))
SSHD_CONFIG = os.path.abspath(os.path.sep.join([DIR_NAME, 'sshd_config']))


class OpenSSHServer(object):

    def __init__(self, port=2222):
        self.port = port
        self.server_proc = None
        _mask = int('0600') if version_info <= (2,) else 0o600
        os.chmod(SERVER_KEY, _mask)
        self.make_config()

    def make_config(self):
        with open(SSHD_CONFIG_TMPL) as fh:
            tmpl = fh.read()
        template = Template(tmpl)
        with open(SSHD_CONFIG, 'w') as fh:
            fh.write(template.render(parent_dir=os.path.abspath(DIR_NAME)))
            fh.write(os.linesep)

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
        del sock

    def stop(self):
        if self.server_proc is not None and self.server_proc.returncode is None:
            self.server_proc.terminate()
            self.server_proc.wait()

    def __del__(self):
        self.stop()
        os.unlink(SSHD_CONFIG)
