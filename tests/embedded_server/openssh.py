# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2022 Panos Kittenis and contributors.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import os
import random
import string
from getpass import getuser
from subprocess import Popen, TimeoutExpired

from gevent import Timeout
from jinja2 import Template

logger = logging.getLogger('pssh.test.openssh_server')
logger.setLevel(logging.DEBUG)


DIR_NAME = os.path.dirname(__file__)
PDIR_NAME = os.path.dirname(DIR_NAME)
PPDIR_NAME = os.path.dirname(PDIR_NAME)
SERVER_KEY = os.path.abspath(os.path.sep.join([DIR_NAME, 'rsa.key']))
CA_HOST_KEY = os.path.abspath(os.path.sep.join([DIR_NAME, 'ca_host_key']))
SSHD_CONFIG_TMPL = os.path.abspath(os.path.sep.join(
    [DIR_NAME, 'sshd_config.tmpl']))
SSHD_CONFIG = os.path.abspath(os.path.sep.join([DIR_NAME, 'sshd_config']))
PRINCIPALS_TMPL = os.path.abspath(os.path.sep.join([DIR_NAME, 'principals.tmpl']))
PRINCIPALS = os.path.abspath(os.path.sep.join([DIR_NAME, 'principals']))


class OpenSSHServerError(Exception):
    pass


class OpenSSHServer(object):

    def __init__(self, listen_ip='127.0.0.1', port=2222):
        self.listen_ip = listen_ip
        self.port = port
        self.server_proc = None
        self.random_server = ''.join(random.choice(string.ascii_lowercase + string.digits)
                                     for _ in range(8))
        self.sshd_config = SSHD_CONFIG + '_%s' % self.random_server
        self._fix_masks()
        self.make_config()

    def _fix_masks(self):
        _mask = 0o600
        dir_mask = 0o755
        for _file in [SERVER_KEY, CA_HOST_KEY]:
            os.chmod(_file, _mask)
        for _dir in [DIR_NAME, PDIR_NAME, PPDIR_NAME]:
            os.chmod(_dir, dir_mask)

    def make_config(self):
        user = getuser()
        with open(SSHD_CONFIG_TMPL) as fh:
            tmpl = fh.read()
        template = Template(tmpl)
        with open(self.sshd_config, 'w') as fh:
            fh.write(template.render(parent_dir=os.path.abspath(DIR_NAME),
                                     listen_ip=self.listen_ip,
                                     random_server=self.random_server,
                                     ))
            fh.write(os.linesep)
        with open(PRINCIPALS_TMPL) as fh:
            _princ_tmpl = fh.read()
        princ_tmpl = Template(_princ_tmpl)
        with open(PRINCIPALS, 'w') as fh:
            fh.write(princ_tmpl.render(user=user))
            fh.write(os.linesep)

    def start_server(self):
        cmd = ['/usr/sbin/sshd', '-D', '-p', str(self.port),
               '-h', SERVER_KEY, '-f', self.sshd_config]
        logger.debug("Starting server with %s" % (" ".join(cmd),))
        self.server_proc = Popen(cmd)
        try:
            with Timeout(seconds=5, exception=TimeoutError):
                while True:
                    try:
                        self.server_proc.wait(.1)
                    except TimeoutExpired:
                        break
        except TimeoutError:
            if self.server_proc.stdout is not None:
                logger.error(self.server_proc.stdout.read())
            if self.server_proc.stderr is not None:
                logger.error(self.server_proc.stderr.read())
            raise OpenSSHServerError("Server could not start")

    def stop(self):
        if self.server_proc is not None and self.server_proc.returncode is None:
            try:
                self.server_proc.terminate()
                self.server_proc.wait()
            except OSError:
                pass
        try:
            os.unlink(self.sshd_config)
        except OSError:
            pass

    def __del__(self):
        self.stop()
