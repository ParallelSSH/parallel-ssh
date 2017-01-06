#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2014- Panos Kittenis

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

"""
Embedded SSH server to test our SSH clients.

Implements:
 * Execution of commands via exec_command
 * Public key and password auth
 * Direct TCP tunneling
 * SSH agent forwarding
 * Stub SFTP server from Paramiko
 * Forced authentication failure

Does _not_ support interactive shells, our clients do not use them.

Server private key is hardcoded. Server listen code inspired by demo_server.py in
Paramiko repository.

Server runs asynchronously in its own greenlet. Call `start_server` with a new `multiprocessing.Process` to run it on a new process with its own event loop.

*Warning* - Note that commands, with or without a shell, are actually run on the system running this server. Destructive commands will affect the system as permissions of user running the server allow. **Use at your own risk**.
"""

# from gipc import start_process
from multiprocessing import Process
import sys
if 'threading' in sys.modules:
    del sys.modules['threading']
from gevent import monkey
monkey.patch_all()
import os
import gevent
from gevent import socket
from gevent.event import Event
import sys
import traceback
import logging
import paramiko
import time
import gevent.subprocess
import gevent.hub

from .stub_sftp import StubSFTPServer
from .tunnel import Tunneler

logger = logging.getLogger("embedded_server")
paramiko_logger = logging.getLogger('paramiko.transport')

host_key = paramiko.RSAKey(filename=os.path.sep.join([
    os.path.dirname(__file__), 'rsa.key']))

class Server(paramiko.ServerInterface):
    """Implements :mod:`paramiko.ServerInterface` to provide an
    embedded SSH server implementation.

    Start a `Server` with at least a host private key.

    Any SSH2 client with public key or password authentication
    is allowed, only. Interactive shell requests are not accepted.

    Implemented:
    * Direct tcp-ip channels (tunneling)
    * SSH Agent forwarding on request
    * PTY requests
    * Exec requests (run a command on server)

    Not Implemented:
    * Interactive shell requests
    """

    def __init__(self, host_key, fail_auth=False,
                 ssh_exception=False,
                 socket=None,
                 port=0,
                 host='127.0.0.1',
                 timeout=None):
        if not socket:
            self.socket = make_socket(host, port)
        if not self.socket:
            msg = "Could not establish listening connection on %s:%s"
            logger.error(msg, host, port)
            raise Exception(msg, host, port)
        self.host = host
        self.port = self.socket.getsockname()[1]
        self.event = Event()
        self.fail_auth = fail_auth
        self.ssh_exception = ssh_exception
        self.host_key = host_key
        self.transport = None
        self.timeout = timeout

    def start_listening(self):
        try:
            gevent.sleep(0)
            self.socket.listen(100)
            logger.info('Listening for connection on %s:%s..', self.host,
                        self.port)
        except Exception as e:
            logger.error('*** Listen failed: %s' % (str(e),))
            traceback.print_exc()
            raise
        gevent.sleep()
        conn, addr = self.socket.accept()
        gevent.sleep(.2)
        logger.info('Got connection..')
        # import ipdb; ipdb.set_trace()
        gevent.sleep(.2)
        if self.timeout:
            logger.debug("SSH server sleeping for %s then raising socket.timeout",
                         self.timeout)
            gevent.Timeout(self.timeout).start()
        self.transport = paramiko.Transport(conn)
        self.transport.load_server_moduli()
        self.transport.add_server_key(self.host_key)
        self.transport.set_subsystem_handler('sftp', paramiko.SFTPServer,
                                             StubSFTPServer)
        gevent.sleep()
        try:
            self.transport.start_server(server=self)
        except paramiko.SSHException as e:
            logger.exception('SSH negotiation failed')
            raise
        gevent.sleep(0)

    def run(self):
        while True:
            try:
                self.start_listening()
                gevent.sleep(0)
            except Exception:
                logger.exception("Error occured starting server")
                continue
            gevent.sleep(0)
            try:
                self.accept_connections()
                gevent.sleep(0)
            except Exception as e:
                logger.error('*** Caught exception: %s: %s' % (str(e.__class__), str(e),))
                traceback.print_exc()
                try:
                    self.transport.close()
                except Exception:
                    pass
                raise

    def accept_connections(self):
        while True:
            gevent.sleep(0)
            channel = self.transport.accept(20)
            if not channel:
                logger.error("Could not establish channel on %s:%s",
                             self.host, self.port)
                gevent.sleep(0)
                continue
            while self.transport.is_active():
                logger.debug("Transport active, waiting..")
                gevent.sleep(1)
            while not channel.send_ready():
                gevent.sleep(.2)
            channel.close()
            gevent.sleep(0)

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_auth_password(self, username, password):
        if self.fail_auth:
            return paramiko.AUTH_FAILED
        if self.ssh_exception:
            raise paramiko.SSHException()
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        if self.fail_auth:
            return paramiko.AUTH_FAILED
        if self.ssh_exception:
            raise paramiko.SSHException()
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return 'password,publickey'

    def check_channel_shell_request(self, channel):
        return False

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth,
                                  pixelheight, modes):
        return True

    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        # import ipdb; ipdb.set_trace()
        logger.debug("Proxy connection %s -> %s requested", origin, destination,)
        extra = {'username' : self.transport.get_username()}
        logger.debug("Starting proxy connection %s -> %s",
                     origin, destination, extra=extra)
        self.event.set()
        try:
            gevent.sleep(.2)
            tunnel = Process(target=Tunneler, args=(destination, self.transport, chanid,))
            tunnel.daemon = True
            tunnel.start()
            gevent.sleep(.2)
        except Exception as ex:
            logger.error("Error creating proxy connection to %s - %s",
                         destination, ex,)
            return paramiko.OPEN_FAILED_CONNECT_FAILED
        gevent.sleep(2)
        return paramiko.OPEN_SUCCEEDED

    def check_channel_forward_agent_request(self, channel):
        logger.debug("Forward agent key request for channel %s" % (channel,))
        gevent.sleep(0)
        return True

    def check_channel_exec_request(self, channel, cmd,
                                   encoding='utf-8'):
        logger.debug("Got exec request on channel %s for cmd %s" % (channel, cmd,))
        self.event.set()
        _env = os.environ
        _env['PYTHONIOENCODING'] = encoding
        process = gevent.subprocess.Popen(cmd, stdout=gevent.subprocess.PIPE,
                                          stdin=gevent.subprocess.PIPE,
                                          shell=True, env=_env)
        gevent.spawn(self._read_response, channel, process)
        gevent.sleep(0)
        return True

    def _read_response(self, channel, process):
        gevent.sleep(0)
        logger.debug("Waiting for output")
        for line in process.stdout:
            channel.send(line)
        process.communicate()
        channel.send_exit_status(process.returncode)
        logger.debug("Command finished with return code %s", process.returncode)
        # Let clients consume output from channel before closing
        gevent.sleep(.1)
        channel.close()
        gevent.sleep(0)

def make_socket(listen_ip, port=0):
    """Make socket on given address and available port chosen by OS"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((listen_ip, port))
    except Exception as e:
        logger.error('Failed to bind to address - %s' % (str(e),))
        traceback.print_exc()
        return
    return sock

def start_server(listen_ip, fail_auth=False, ssh_exception=False,
                 timeout=None,
                 listen_port=0):
    # gevent.reinit()
    gevent.hub.reinit()
    # h.destroy(destroy_loop=True)
    # h = gevent.hub.Hub()
    # h.NOT_ERROR = (Exception,)
    # gevent.hub.set_hub(h)
    server = Server(host_key, host=listen_ip, port=listen_port,
                    fail_auth=fail_auth, ssh_exception=ssh_exception,
                    timeout=timeout)
    try:
        server.run()
    except KeyboardInterrupt:
        sys.exit(0)
    # listen_process = Process(target=server.run)
    # listen_process.start()
    # listen_process.join()

def start_server_process(listen_ip, fail_auth=False, ssh_exception=False,
                         timeout=None, listen_port=0):
    gevent.reinit()
    server = Process(target=start_server, args=(listen_ip,),
                     kwargs={
                         'listen_port': listen_port,
                         'fail_auth': fail_auth,
                         'ssh_exception': ssh_exception,
                         'timeout': timeout,
                         })
    server.start()
    gevent.sleep(.2)
    return server
