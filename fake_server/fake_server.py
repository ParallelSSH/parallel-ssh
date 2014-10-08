#!/usr/bin/env python

# This file is part of parallel-ssh.

# Copyright (C) 2014 Panos Kittenis

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
Fake SSH server to test our SSH clients.
Supports execution of commands via exec_command. Does _not_ support interactive \
shells, our clients do not use them.
Server private key is hardcoded, server listen code inspired by demo_server.py in \
paramiko repository
"""

import gevent
from gevent import monkey
monkey.patch_all()
import os
from gevent import socket
from gevent.event import Event
import sys
import traceback
import logging
import paramiko
import time
from stub_sftp import StubSFTPServer

logger = logging.getLogger("fake_server")
paramiko_logger = logging.getLogger('paramiko.transport')

host_key = paramiko.RSAKey(filename = os.path.sep.join([os.path.dirname(__file__), 'rsa.key']))

class Server (paramiko.ServerInterface):
    def __init__(self, cmd_req_response = {}, fail_auth = False):
        self.event = Event()
        self.cmd_req_response = cmd_req_response
        self.fail_auth = fail_auth

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_auth_password(self, username, password):
        if self.fail_auth: return paramiko.AUTH_FAILED
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        if self.fail_auth: return paramiko.AUTH_FAILED
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return 'password,publickey'

    def check_channel_shell_request(self, channel):
        return False

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth,
                                  pixelheight, modes):
        return True

    def check_channel_forward_agent_request(self, channel):
        logger.debug("Forward agent key request for channel %s" % (channel,))
        return True

    def check_channel_exec_request(self, channel, cmd):
        logger.debug("Got exec request on channel %s for cmd %s" % (channel, cmd,))
        # Remove any 'bash -c' and/or quotes from command
        cmd = cmd.replace('bash -c \"', "")
        cmd = cmd.replace('\"', "")
        if not cmd in self.cmd_req_response:
            return False
        self.event.set()
        # Check if response is an iterator in which case we
        # do not return but read from iterator and send responses.
        # This is to simulate a long running command that has not
        # finished executing yet.
        if hasattr(self.cmd_req_response[cmd], 'next'):
            gevent.spawn(self._long_running_response,
                         channel, self.cmd_req_response[cmd])
        else:
            response = self.cmd_req_response[cmd] + os.linesep
            channel.send_exit_status(0)
        return True

    def _long_running_response(self, channel, responder):
        for response in responder:
            channel.send(response + os.linesep)
            gevent.sleep(0)
        channel.send_exit_status(0)
        channel.close()

def make_socket(listen_ip):
    """Make socket on given address and available port chosen by OS"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((listen_ip, 0))
    except Exception, e:
        logger.error('Failed to bind to address - %s' % (str(e),))
        traceback.print_exc()
        return
    return sock

def listen(cmd_req_response, sock, fail_auth = False):
    """Run a fake ssh server and given a cmd_to_run, send given \
    response to client connection. Returns (server, socket) tuple \
    where server is a joinable server thread and socket is listening \
    socket of server."""
    listen_ip, listen_port = sock.getsockname()
    if not sock:
        logger.error("Could not establish listening connection on %s:%s", listen_ip, listen_port)
        return 
    try:
        sock.listen(100)
        logger.info('Listening for connection on %s:%s..', listen_ip, listen_port)
    except Exception, e:
        logger.error('*** Listen failed: %s' % (str(e),))
        traceback.print_exc()
        return
    handle_ssh_connection(cmd_req_response, sock, fail_auth=fail_auth)

def _handle_ssh_connection(cmd_req_response, transport, fail_auth = False):
    try:
        transport.load_server_moduli()
    except:
        return
    transport.add_server_key(host_key)
    transport.set_subsystem_handler('sftp', paramiko.SFTPServer, StubSFTPServer)
    server = Server(cmd_req_response = cmd_req_response, fail_auth = fail_auth)
    try:
        transport.start_server(server=server)
    except paramiko.SSHException, e:
        logger.exception('SSH negotiation failed')
        return
    except Exception:
        logger.exception("Error occured starting server")
        return
    channel = transport.accept(20)
    if not channel:
        logger.error("Could not establish channel")
        return
    while transport.is_active():
        time.sleep(1)
    while not channel.send_ready():
        time.sleep(.5)
    channel.close()
    
def handle_ssh_connection(cmd_req_response, sock, fail_auth = False):
    conn, addr = sock.accept()
    logger.info('Got connection..')
    try:
        transport = paramiko.Transport(conn)
        _handle_ssh_connection(cmd_req_response, transport, fail_auth=fail_auth)
    except Exception, e:
        logger.error('*** Caught exception: %s: %s' % (str(e.__class__), str(e),))
        traceback.print_exc()
        try:
            transport.close()
        except:
            pass
        return

def start_server(cmd_req_response, sock, fail_auth=False):
    return gevent.spawn(listen, cmd_req_response, sock, fail_auth=fail_auth)

if __name__ == "__main__":
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    sock = make_socket('127.0.0.1')
    server = start_server({'fake' : 'fake response'}, sock)
    try:
        server.join()
    except KeyboardInterrupt:
        sys.exit(0)
