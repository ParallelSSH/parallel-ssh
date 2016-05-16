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
Generic 'Tunneler' module for tunneling between source <-> destination
network connections asynchronously with gevent.
"""

import gevent
from gevent import socket, select
import logging

logger = logging.getLogger("fake_server")

class Tunneler(gevent.Greenlet):    
    def __init__(self, address, transport, chanid):
        gevent.Greenlet.__init__(self)
        self.socket = socket.create_connection(address)
        self.transport = transport
        self.chanid = chanid

    def close(self):
        try:
            self.transport.close()
        except Exception:
            pass
        return

    def tunnel(self, dest_socket, source_chan):
        try:
            while True:
                logger.debug("Tunnel waiting for data..")
                data = source_chan.recv(1024)
                dest_socket.sendall(data)
                gevent.sleep(.1)
                response_data = dest_socket.recv(1024)
                source_chan.sendall(response_data)
                logger.debug("Tunnel sent data..")
                gevent.sleep(0)
        finally:
            source_chan.close()
            dest_socket.close()

    def run(self):
        channel = self.transport.accept(20)
        if not channel:
            return
        if not channel.get_id() == self.chanid:
            return
        peer = self.socket.getpeername()
        logger.debug("Start tunneling with peer %s, user %s", peer,
                     self.transport.get_username())
        try:
            self.tunnel(self.socket, channel)
        except Exception, ex:
            logger.exception("Got exception creating tunnel - %s", ex,)
        logger.debug("Finished tunneling")
