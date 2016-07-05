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

Server private key is hardcoded. Server listen code inspired by demo_server.py in \
Paramiko repository.

Server runs asynchronously in its own greenlet. Call `start_server` with a new `multiprocessing.Process` to run it on a new process with its own event loop.

*Warning* - Note that commands, with or without a shell, are actually run on the system running this server. Destructive commands will actually affect the system as permissions of user running the server allow. *Use at your own risk*.
"""

import sys
if 'threading' in sys.modules:
    del sys.modules['threading']
import gevent
import os
import socket
from gevent import socket
from gevent.event import Event
import sys
import traceback
import logging
import paramiko
import time
from .stub_sftp import StubSFTPServer
from .tunnel import Tunneler
import gevent.subprocess

logger = logging.getLogger("embedded_server")
paramiko_logger = logging.getLogger('paramiko.transport')

host_key = paramiko.RSAKey(filename = os.path.sep.join([os.path.dirname(__file__), 'rsa.key']))

class Server(paramiko.ServerInterface):
    def __init__(self, transport, fail_auth=False,
                 ssh_exception=False):
        self.event = Event()
        self.fail_auth = fail_auth
        self.ssh_exception = ssh_exception
        self.transport = transport

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
        logger.debug("Proxy connection %s -> %s requested", origin, destination,)
        extra = {'username' : self.transport.get_username()}
        logger.debug("Starting proxy connection %s -> %s",
                     origin, destination, extra=extra)
        try:
            tunnel = Tunneler(destination, self.transport, chanid)
            tunnel.start()
        except Exception, ex:
            logger.error("Error creating proxy connection to %s - %s",
                         destination, ex,)
            return paramiko.OPEN_FAILED_CONNECT_FAILED
        return paramiko.OPEN_SUCCEEDED

    def check_channel_forward_agent_request(self, channel):
        logger.debug("Forward agent key request for channel %s" % (channel,))
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
        return True

    def _read_response(self, channel, process):
        for line in process.stdout:
            channel.send(line)
        process.communicate()
        channel.send_exit_status(process.returncode)
        logger.debug("Command finished with return code %s", process.returncode)
        # Let clients consume output from channel before closing
        gevent.sleep(.2)
        channel.close()

def make_socket(listen_ip, port=0):
    """Make socket on given address and available port chosen by OS"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((listen_ip, port))
    except Exception, e:
        logger.error('Failed to bind to address - %s' % (str(e),))
        traceback.print_exc()
        return
    return sock

def listen(sock, fail_auth=False, ssh_exception=False,
           timeout=None):
    """Run server and given a cmd_to_run, send given
    response to client connection. Returns (server, socket) tuple
    where server is a joinable server thread and socket is listening
    socket of server.
    """
    listen_ip, listen_port = sock.getsockname()
    if not sock:
        logger.error("Could not establish listening connection on %s:%s",
                     listen_ip, listen_port)
        return 
    try:
        sock.listen(100)
        logger.info('Listening for connection on %s:%s..', listen_ip,
                    listen_port)
    except Exception, e:
        logger.error('*** Listen failed: %s' % (str(e),))
        traceback.print_exc()
        return
    handle_ssh_connection(sock, fail_auth=fail_auth,
                          timeout=timeout, ssh_exception=ssh_exception)

def _handle_ssh_connection(transport, fail_auth=False,
                           ssh_exception=False):
    try:
        transport.load_server_moduli()
    except:
        return
    transport.add_server_key(host_key)
    transport.set_subsystem_handler('sftp', paramiko.SFTPServer, StubSFTPServer)
    server = Server(transport,
                    fail_auth=fail_auth, ssh_exception=ssh_exception)
    try:
        transport.start_server(server=server)
    except paramiko.SSHException, e:
        logger.exception('SSH negotiation failed')
        return
    except Exception:
        logger.exception("Error occured starting server")
        return
    gevent.sleep(0)
    channel = transport.accept(20)
    if not channel:
        logger.error("Could not establish channel")
        return
    while transport.is_active():
        logger.debug("Transport active, waiting..")
        gevent.sleep(1)
    while not channel.send_ready():
        gevent.sleep(.2)
    channel.close()

def handle_ssh_connection(sock,
                          fail_auth=False, ssh_exception=False,
                          timeout=None):
    conn, addr = sock.accept()
    logger.info('Got connection..')
    if timeout:
        logger.debug("SSH server sleeping for %s then raising socket.timeout",
                    timeout)
        gevent.Timeout(timeout).start()
    try:
        transport = paramiko.Transport(conn)
        _handle_ssh_connection(transport, fail_auth=fail_auth,
                               ssh_exception=ssh_exception)
    except Exception, e:
        logger.error('*** Caught exception: %s: %s' % (str(e.__class__), str(e),))
        traceback.print_exc()
        try:
            transport.close()
        except:
            pass
        return

def start_server(sock, fail_auth=False, ssh_exception=False,
                 timeout=None):
    return gevent.spawn(listen, sock, fail_auth=fail_auth,
                        timeout=timeout, ssh_exception=ssh_exception)

if __name__ == "__main__":
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    sock = make_socket('127.0.0.1')
    server = start_server(sock)
    try:
        server.join()
    except KeyboardInterrupt:
        sys.exit(0)
