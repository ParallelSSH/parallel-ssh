# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2020 Panos Kittenis.
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

from threading import Thread, Event
from queue import Queue

from gevent import spawn, joinall, get_hub, sleep
from gevent.server import StreamServer
from gevent.select import poll, POLLIN, POLLOUT
from ssh2.session import LIBSSH2_SESSION_BLOCK_INBOUND, LIBSSH2_SESSION_BLOCK_OUTBOUND
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from ...constants import DEFAULT_RETRIES


logger = logging.getLogger(__name__)


class LocalForwarder(Thread):

    def __init__(self):
        """Thread runner for a group of local port forwarding proxies.

        Starts servers in their own gevent hub via thread run target.

        Input ``(SSHClient, target_host, target_port)`` tuples to ``in_q`` to create new servers
        and get port to connect to via ``out_q`` once a target has been put into the input queue.

        ``SSHClient`` is the client for the SSH host that will be proxying.
        """
        Thread.__init__(self)
        self.in_q = Queue(1)
        self.out_q = Queue(1)
        self._servers = {}
        self._hub = None
        self.started = Event()
        self._cleanup_let = None

    def _start_server(self):
        client, host, port = self.in_q.get()
        server = TunnelServer(client, host, port)
        server.start()
        while not server.started:
            sleep(0.01)
        self._servers[client] = server
        local_port = server.socket.getsockname()[1]
        self.out_q.put(local_port)

    def shutdown(self):
        for client, server in self._servers.items():
            server.stop()

    def _cleanup_servers(self):
        while True:
            for client, server in self._servers.items():
                if client.sock.closed:
                    server.stop()
                    del self._servers[client]
            sleep(60)

    def run(self):
        """Thread runner ensures a non main hub has been created for all subsequent
        greenlets and waits for (client, host, port) tuples to be put into self.in_q.

        A server is created once something is in the queue and the port to connect to
        is put into self.out_q.
        """
        self._hub = get_hub()
        assert self._hub.main_hub is False
        self.started.set()
        self._cleanup_let = spawn(self._cleanup_servers)
        logger.debug("Hub in server runner is main hub: %s", self._hub.main_hub)
        try:
            while True:
                if self.in_q.empty():
                    sleep(.01)
                    continue
                self._start_server()
        except Exception:
            logger.error("Tunnel thread caught exception and will exit:",
                         exc_info=1)
            self.shutdown()


class TunnelServer(StreamServer):
    """Local port forwarding server for tunneling connections from remote SSH server.

    Accepts connections on an available bind_address port once started and tunnels data
    to/from remote SSH host for each connection.
    """

    def __init__(self, client, host, port, bind_address='127.0.0.1', timeout=0.1):
        StreamServer.__init__(self, (bind_address, 0), self._read_rw)
        self.client = client
        self.host = host
        self.port = port
        self.session = client.session
        self._retries = DEFAULT_RETRIES
        self.timeout = timeout

    def _read_rw(self, socket, address):
        local_addr, local_port = address
        logger.debug("Client connected, forwarding %s:%s on"
                     " remote host to %s:%s",
                     self.host, self.port, local_addr, local_port)
        try:
            channel = self._open_channel_retries(
                self.host, self.port, local_port)
        except Exception as ex:
            logger.error("Could not establish channel to %s:%s: %s",
                         self.host, self.port, ex)
            self.exception = ex
            return
        source = spawn(self._read_forward_sock, socket, channel)
        dest = spawn(self._read_channel, socket, channel)
        logger.debug("Waiting for read/write greenlets")
        self._source_let = source
        self._dest_let = dest
        self._wait_send_receive_lets(source, dest, channel, socket)

    def _wait_send_receive_lets(self, source, dest, channel, forward_sock):
        try:
            joinall((source, dest), raise_error=True)
        finally:
            logger.debug("Closing channel and forward socket")
            while channel is not None and channel.close() == LIBSSH2_ERROR_EAGAIN:
                self.poll(timeout=.5)
            forward_sock.close()

    def _read_forward_sock(self, forward_sock, channel):
        while True:
            if channel is None or channel.eof():
                logger.debug("Channel closed, tunnel forward socket reader exiting")
                return
            try:
                data = forward_sock.recv(1024)
            except Exception as ex:
                logger.error("Forward socket read error: %s", ex)
                raise
            data_len = len(data)
            # logger.debug("Read %s data from forward socket", data_len,)
            if data_len == 0:
                sleep(.01)
                continue
            data_written = 0
            while data_written < data_len:
                try:
                    rc, bytes_written = channel.write(data[data_written:])
                except Exception as ex:
                    logger.error("Channel write error: %s", ex)
                    raise
                data_written += bytes_written
                if rc == LIBSSH2_ERROR_EAGAIN:
                    self.poll()
            logger.debug("Wrote all data to channel")

    def _read_channel(self, forward_sock, channel):
        while True:
            if channel is None or channel.eof():
                logger.debug("Channel closed, tunnel reader exiting")
                return
            try:
                size, data = channel.read()
            except Exception as ex:
                logger.error("Error reading from channel - %s", ex)
                raise
            # logger.debug("Read %s data from channel" % (size,))
            if size == LIBSSH2_ERROR_EAGAIN:
                self.poll()
                continue
            elif size == 0:
                sleep(.01)
                continue
            try:
                forward_sock.sendall(data)
            except Exception as ex:
                logger.error(
                    "Error sending data to forward socket - %s", ex)
                raise
            logger.debug("Wrote %s data to forward socket", len(data))

    def _open_channel(self, fw_host, fw_port, local_port):
        channel = self.session.direct_tcpip_ex(
            fw_host, fw_port, '127.0.0.1',
            local_port)
        while channel == LIBSSH2_ERROR_EAGAIN:
            self.poll()
            channel = self.session.direct_tcpip_ex(
                fw_host, fw_port, '127.0.0.1',
                local_port)
        return channel

    def _open_channel_retries(self, fw_host, fw_port, local_port,
                              wait_time=0.1):
        num_tries = 0
        while num_tries < self._retries:
            try:
                channel = self._open_channel(fw_host, fw_port, local_port)
            except Exception:
                num_tries += 1
                logger.error("Error opening channel to %s:%s, retries %s/%s",
                             fw_host, fw_port, num_tries, self._retries)
                if num_tries >= self._retries:
                    raise
                sleep(wait_time)
                wait_time *= 5
                continue
            return channel

    def poll(self, timeout=None):
        """Perform co-operative gevent poll on ssh2 session socket.

        Blocks current greenlet only if socket has pending read or write operations
        in the appropriate direction.
        """
        directions = self.session.block_directions()
        if directions == 0:
            return
        events = 0
        if directions & LIBSSH2_SESSION_BLOCK_INBOUND:
            events = POLLIN
        if directions & LIBSSH2_SESSION_BLOCK_OUTBOUND:
            events |= POLLOUT
        self._poll_socket(self.session.sock, events, timeout=timeout)

    def _poll_socket(self, sock, events, timeout=None):
        # gevent.select.poll converts seconds to miliseconds to match python socket
        # implementation
        timeout = timeout * 1000 if timeout is not None else 100
        poller = poll()
        poller.register(sock, eventmask=events)
        return poller.poll(timeout=timeout)


FORWARDER = LocalForwarder()
FORWARDER.daemon = True
