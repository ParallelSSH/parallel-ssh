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
from queue import Queue
from threading import Thread, Event

from gevent import spawn, joinall, get_hub, sleep
from gevent.server import StreamServer
from gevent.event import Event as GEvent
from gevent.pool import Pool
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from ...constants import DEFAULT_RETRIES

logger = logging.getLogger(__name__)


class LocalForwarder(Thread):

    def __init__(self):
        """Thread runner for a group of local port forwarding proxies.

        Starts servers in their own gevent hub via thread run target.

        Use ``enqueue`` to create new servers
        and get port to connect to via ``out_q`` once a target has been put into the input queue.

        ``SSHClient`` is the client for the SSH host that will be proxying.

        There can be as many LocalForwarder(s) as needed to scale.

        Relationship of clients to forwarders to servers is

        One client -> One Forwarder -> Many Servers <-> Many proxy hosts -> one target host per proxy host

        A Forwarder starts servers. Servers communicate with clients directly via Forwarder thread.

        Multiple forwarder threads can be used to scale clients to more threads.
        """
        Thread.__init__(self)
        self.in_q = Queue(1)
        self.out_q = Queue(1)
        self._servers = {}
        self._hub = None
        self.started = Event()
        self.shutdown_triggered = Event()
        self._cleanup_let = None

    def _start_server(self):
        client, host, port = self.in_q.get()
        logger.debug("Starting server for %s:%s", host, port)
        server = TunnelServer(client, host, port)
        self._servers[client] = server
        server.start()
        self._get_server_listen_port(server)

    def _get_server_listen_port(self, server):
        while not server.started:
            sleep(0.01)
        local_port = server.listen_port
        self.out_q.put(local_port)

    def enqueue(self, client, host, port):
        """Add target host:port to tunnel via client to queue.

        :param client: The client to connect via.
        :type client: :py:mod:`pssh.clients.native.single.SSHClient`
        :param host: Target host to open connection to.
        :type host: str
        :param port: Target port to connect on.
        :type port: int
        """
        self.in_q.put((client, host, port))

    def shutdown(self):
        """Stop all tunnel servers."""
        pass
        # if self._cleanup_let is not None and self._cleanup_let.started:
        #     self._cleanup_let.kill()
        # for client, server in self._servers.items():
        #     server.stop()
        # client.session = None
        # client.sock = None

    def _cleanup_servers_let(self):
        while True:
            self._cleanup_servers()
            sleep(60)

    def _cleanup_servers(self):
        for client in list(self._servers.keys()):
            if client.sock is None or client.sock.closed:
                self.cleanup_server(client)

    def run(self):
        """Thread runner ensures a non main hub has been created for all subsequent
        greenlets and waits for (client, host, port) tuples to be put into self.in_q.

        A server is created once something is in the queue and the port to connect to
        is put into self.out_q.
        """
        self._hub = get_hub()
        assert self._hub.main_hub is False
        self.started.set()
        # self._cleanup_let = spawn(self._cleanup_servers_let)
        logger.debug("Hub in server runner is main hub: %s", self._hub.main_hub)
        try:
            while True:
                if self.shutdown_triggered.is_set():
                    logger.debug("Forwarder shutdown triggered - exiting forwarder thread")
                    # self.shutdown()
                    return
                if self.in_q.empty():
                    sleep(.01)
                    continue
                self._start_server()
        except Exception:
            logger.exception("Tunnel thread caught exception and will exit:")
            self.shutdown()

    def cleanup_server(self, client):
        """The purpose of this function is for a proxied client to notify the LocalForwarder that it
         is shutting down and its corresponding server can also be shut down."""
        server = self._servers[client]
        server.stop()
        del self._servers[client]
        if not self._servers:
            logger.debug("Forwarder has no active servers remaining - shutting down forwarder thread")
            self.shutdown_triggered.set()


class TunnelServer(StreamServer):
    """Local port forwarding server for tunneling connections from remote SSH server.

    Accepts connections on an available bind_address port once started and tunnels data
    to/from remote SSH host for each connection.
    """

    def __init__(self, client, host, port, bind_address='127.0.0.1',
                 num_retries=DEFAULT_RETRIES):
        self._pool = Pool()
        StreamServer.__init__(self, (bind_address, 0), self._read_rw, spawn=self._pool)
        self.client = client
        self.host = host
        self.port = port
        self.session = client.session
        self._client = client
        self._retries = num_retries
        self.bind_address = bind_address
        self.exception = None
        self._server_shutdown = Event()
        # self._channel = None

    @property
    def listen_port(self):
        return self.socket.getsockname()[1] if self.socket is not None else None

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
        # Keep channel alive while server is running
        source = self._pool.spawn(self._read_forward_sock, socket, channel)
        dest = self._pool.spawn(self._read_channel, socket, channel)
        logger.debug("Waiting for read/write greenlets")
        self._source_let = source
        self._dest_let = dest
        self._wait_send_receive_lets(source, dest, channel)
        # self._client.eagain(channel.close)

    def _wait_send_receive_lets(self, source, dest, channel):
        joinall((source, dest), raise_error=True)
        # self._channel = None
        # self.client.sock.close()
        # try:
        #     joinall((source, dest), raise_error=True)
        # finally:
        #     logger.debug("Closing channel")
        #     self._client.close_channel(channel)
        # # self.client.sock.close()

    def _read_forward_sock(self, forward_sock, channel):
        while True:
            if channel is None or channel.eof():
                logger.debug("Channel closed, tunnel forward socket reader exiting")
                return
            if not forward_sock or forward_sock.closed:
                logger.debug("Forward socket closed, tunnel forward socket reader exiting")
                return
            if self._server_shutdown.is_set():
                logger.debug("Server shutdown initiated, tunnel forward socket reader exiting")
                return
            try:
                data = forward_sock.recv(1024)
            except Exception as ex:
                logger.error("Forward socket read error: %s", ex)
                raise
            data_len = len(data)
            logger.debug("Read %s data from forward socket, socket is closed: %s", data_len, forward_sock.closed)
            # logger.debug("Data from socket: %s", data.decode('utf-8'))
            # if data_len == 36:
            #     print("=========================== Data from socket: %s", data.decode('utf-8'))
            if data_len == 0:
                if self._server_shutdown.is_set():
                    return
                sleep(.01)
                continue
            # if channel is None or channel.eof() or self.client.sock is None or self.client.sock.closed:
            #     return
            try:
                self._client.eagain_write(channel.write, data)
            except Exception as ex:
                logger.error("Error writing data to channel - %s", ex)
                raise
            logger.debug("Wrote all data to channel")
            # logger.debug("Data from socket: %s", data.decode('utf-8'))

    def _read_channel(self, forward_sock, channel):
        while True:
            if channel is None or channel.eof():
                logger.debug("Channel closed, tunnel reader exiting")
                return
            if self._server_shutdown.is_set():
                logger.debug("Server shutdown initiated, tunnel reader exiting")
                return
            try:
                size, data = channel.read()
            except Exception as ex:
                logger.error("Error reading from channel - %s", ex)
                raise
            if size == LIBSSH2_ERROR_EAGAIN:
                self._client.poll()
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
            fw_host, fw_port, self.bind_address,
            local_port)
        while channel == LIBSSH2_ERROR_EAGAIN:
            self._client.poll()
            channel = self.session.direct_tcpip_ex(
                fw_host, fw_port, self.bind_address,
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


FORWARDER = LocalForwarder()
FORWARDER.daemon = True
