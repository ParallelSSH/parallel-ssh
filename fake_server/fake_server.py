#!/usr/bin/env python

"""
Fake SSH server to test our SSH clients.
Supports execution of commands via exec_command. Does _not_ support interactive \
shells, our clients do not use them.
Server private key is hardcoded, server listen code inspired by demo_server.py in \
paramiko repository
"""

# import multiprocessing
import gevent
from gevent import monkey
monkey.patch_all()
import os
import socket
from gevent.event import Event
import sys
import traceback
import logging
import paramiko
import time

logger = logging.getLogger(__name__)
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

    def check_channel_exec_request(self, channel, cmd):
        logger.debug("Got exec request on channel %s for cmd %s" % (channel, cmd,))
        # Remove any 'bash -c' and/or quotes from command
        cmd = cmd.replace('bash -c \"', "")
        cmd = cmd.replace('\"', "")
        if not cmd in self.cmd_req_response:
            return False
        channel.send(self.cmd_req_response[cmd])
        channel.send_exit_status(0)
        self.event.set()
        return True

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
    # sock = _make_socket(listen_ip)
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
    accept_thread = gevent.spawn(handle_ssh_connection,
                                 cmd_req_response, sock,
                                 fail_auth=fail_auth)
    # accept_thread.start()
    return accept_thread

def _handle_ssh_connection(cmd_req_response, t, client, addr, fail_auth = False):
    try:
        t.load_server_moduli()
    except:
        return
    t.add_server_key(host_key)
    server = Server(cmd_req_response = cmd_req_response, fail_auth = fail_auth)
    try:
        t.start_server(server=server)
    except paramiko.SSHException, _:
        logger.error('SSH negotiation failed.')
        return
    return _accept_ssh_data(t, server)

def _accept_ssh_data(t, server):
    chan = t.accept(20)
    if not chan:
        logger.error("Could not establish channel")
        return
    logger.info("Authenticated..")
    chan.send_ready()
    server.event.wait(10)
    if not server.event.isSet():
        logger.error('Client never sent command')
        chan.close()
        return
    while not chan.send_ready():
        time.sleep(.5)
    chan.close()
    
def handle_ssh_connection(cmd_req_response, sock, fail_auth = False):
    client, addr = sock.accept()
    logger.info('Got connection..')
    try:
        t = paramiko.Transport(client)
        _handle_ssh_connection(cmd_req_response, t, client, addr, fail_auth=fail_auth)
    except Exception, e:
        logger.error('*** Caught exception: %s: %s' % (str(e.__class__), str(e),))
        traceback.print_exc()
        try:
            t.close()
        except:
            pass
        return

if __name__ == "__main__":
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    sock = make_socket('127.0.0.1')
    server = listen({'fake' : 'fake response' + os.linesep}, sock)
    try:
        server.get()
    except KeyboardInterrupt:
        sys.exit(0)
        
