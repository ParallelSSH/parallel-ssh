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
 * Direct TCP tunneling (port forwarding)
 * SSH agent forwarding
 * Stub SFTP server from Paramiko
 * Forced authentication failure
 * Forced server timeout for connection timeout simulation

Does _not_ support interactive shells - it is intended for purely API driven use.

An embedded private key is provided as `embedded_server.host_key` and may be overriden

Server runs asynchronously in its own greenlet.

*Warning* - Note that commands, with or without a shell, are actually run on the system running this server. Destructive commands will affect the system as permissions of user running the server allow. **Use at your own risk**.

Example Usage
===============

from embedded_server import start_server, start_server_from_ip, make_socket

Make server from existing socket
----------------------------------

socket = make_socket('127.0.0.1')
server = start_server(socket)

Make server from IP and optionally port
-----------------------------------------

server, listen_port = start_server_from_ip('127.0.0.1')
other_server, _ = start_server_from_ip('127.0.0.1', port=1234)
"""

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
import time
import paramiko
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
    embedded SSH2 server implementation.

    Start a `Server` with at least a :mod:`paramiko.Transport` object
    and a host private key.

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

    def __init__(self, transport, host_key, fail_auth=False,
                 ssh_exception=False,
                 encoding='utf-8'):
        paramiko.ServerInterface.__init__(self)
        transport.load_server_moduli()
        transport.add_server_key(host_key)
        transport.set_subsystem_handler('sftp', paramiko.SFTPServer, StubSFTPServer)
        self.transport = transport
        self.event = Event()
        self.fail_auth = fail_auth
        self.ssh_exception = ssh_exception
        self.host_key = host_key
        self.encoding = encoding

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
        except Exception as ex:
            logger.error("Error creating proxy connection to %s - %s",
                         destination, ex,)
            return paramiko.OPEN_FAILED_CONNECT_FAILED
        self.event.set()
        gevent.sleep()
        logger.debug("Proxy connection started")
        return paramiko.OPEN_SUCCEEDED

    def check_channel_forward_agent_request(self, channel):
        logger.debug("Forward agent key request for channel %s" % (channel,))
        gevent.sleep()
        return True

    def check_channel_exec_request(self, channel, cmd):
        logger.debug("Got exec request on channel %s for cmd %s" % (channel, cmd,))
        self.event.set()
        _env = os.environ
        _env['PYTHONIOENCODING'] = self.encoding
        if hasattr(channel, 'environment'):
            _env.update(channel.environment)
        process = gevent.subprocess.Popen(cmd, stdout=gevent.subprocess.PIPE,
                                          stdin=gevent.subprocess.PIPE,
                                          stderr=gevent.subprocess.PIPE,
                                          shell=True, env=_env)
        gevent.spawn(self._read_response, channel, process)
        gevent.sleep(0)
        return True

    def check_channel_env_request(self, channel, name, value):
        if not hasattr(channel, 'environment'):
            channel.environment = {}
        channel.environment.update({
            name.decode(self.encoding): value.decode(self.encoding)})
        return True

    def _read_response(self, channel, process):
        gevent.sleep(0)
        logger.debug("Waiting for output")
        for line in process.stdout:
            channel.send(line)
        for line in process.stderr:
            channel.send_stderr(line)
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
    except Exception as ex:
        logger.error('Failed to bind to address - %s', ex)
        traceback.print_exc()
        return
    return sock

def listen(sock, fail_auth=False, ssh_exception=False,
           timeout=None,
           encoding='utf-8'):
    """Run server and given a cmd_to_run, send given
    response to client connection. Returns (server, socket) tuple
    where server is a joinable server thread and socket is listening
    socket of server.
    """
    # sock = make_socket(ip, port=port)
    try:
        sock.listen(100)
    except Exception as e:
        logger.error('*** Listen failed: %s' % (str(e),))
        traceback.print_exc()
        return
    host, port = sock.getsockname()
    logger.info('Listening for connection on %s:%s..', host, port)
    return handle_ssh_connection(
        sock, fail_auth=fail_auth, timeout=timeout, ssh_exception=ssh_exception,
        encoding=encoding)

def _handle_ssh_connection(transport, fail_auth=False,
                           ssh_exception=False,
                           encoding='utf-8'):
    server = Server(transport, host_key,
                    fail_auth=fail_auth, ssh_exception=ssh_exception,
                    encoding=encoding)
    try:
        transport.start_server(server=server)
    except paramiko.SSHException as e:
        logger.exception('SSH negotiation failed')
        return
    except Exception:
        logger.exception("Error occured starting server")
        return
    # *Important* Allow other greenlets to execute before establishing connection
    # which may be handled by said other greenlets
    gevent.sleep(2)
    channel = transport.accept(20)
    gevent.sleep(0)
    if not channel:
        logger.error("Could not establish channel")
        return
    while transport.is_active():
        logger.debug("Transport active, waiting..")
        gevent.sleep(1)
    while not channel.send_ready():
        gevent.sleep(.2)
    channel.close()
    gevent.sleep(0)

def handle_ssh_connection(sock,
                          fail_auth=False, ssh_exception=False,
                          timeout=None,
                          encoding='utf-8'):
    conn, addr = sock.accept()
    logger.info('Got connection..')
    if timeout:
        logger.debug("SSH server sleeping for %s then raising socket.timeout",
                    timeout)
        gevent.Timeout(timeout).start().get()
    try:
        transport = paramiko.Transport(conn)
        return _handle_ssh_connection(transport, fail_auth=fail_auth,
                                      ssh_exception=ssh_exception,
                                      encoding=encoding)
    except Exception as e:
        logger.error('*** Caught exception: %s: %s' % (str(e.__class__), str(e),))
        traceback.print_exc()
        try:
            transport.close()
        except Exception:
            pass

def start_server(sock, fail_auth=False, ssh_exception=False,
                 timeout=None,
                 encoding='utf-8'):
    return gevent.spawn(listen, sock, fail_auth=fail_auth,
                        timeout=timeout, ssh_exception=ssh_exception,
                        encoding=encoding)

def start_server_from_ip(ip, port=0,
                         fail_auth=False, ssh_exception=False,
                         timeout=None,
                         encoding='utf-8'):
    server_sock = make_socket(ip, port=port)
    server = start_server(server_sock, fail_auth=fail_auth,
                          ssh_exception=ssh_exception, timeout=timeout,
                          encoding=encoding)
    return server, server_sock.getsockname()[1]
