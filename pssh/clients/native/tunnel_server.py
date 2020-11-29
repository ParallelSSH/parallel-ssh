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

from gevent import socket, spawn, joinall, get_hub, sleep, Timeout as GTimeout
from gevent.server import StreamServer
from gevent.select import poll, select, POLLIN, POLLOUT
from ssh2.session import Session, LIBSSH2_SESSION_BLOCK_INBOUND, LIBSSH2_SESSION_BLOCK_OUTBOUND
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from .single import SSHClient
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)


class TunnelServer(StreamServer):

    def __init__(self, client):
        StreamServer.__init__(self, ('127.0.0.1', 0), self.read_rw)
        self.client = client
        self.session = client.session
        self._retries = DEFAULT_RETRIES
        # logger.debug("Started server on %s")

    def read_rw(self, socket, address):
        logger.debug("Client connected, forwarding %s:%s on"
                     " remote host to %s",
                     self.client.host, self.client.port, address)
        local_port = address[1]
        try:
            channel = self._open_channel_retries(
                self.client.host, self.client.port, local_port)
        except Exception as ex:
            logger.error("Could not establish channel to %s:%s: %s",
                         self.client.host, self.client.port, ex)
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
        except Exception as ex:
            logger.error(ex)
        finally:
            logger.debug("Closing channel and forward socket")
            channel.close()
            forward_sock.close()

    def _open_channel(self, fw_host, fw_port, local_port):
        channel = self.session.direct_tcpip_ex(
            fw_host, fw_port, '127.0.0.1',
            local_port)
        while channel == LIBSSH2_ERROR_EAGAIN:
            select((self.client.sock,), (self.client.sock,), ())
            channel = self.session.direct_tcpip_ex(
                fw_host, fw_port, '127.0.0.1',
                local_port)
        return channel

    def _read_forward_sock(self, forward_sock, channel):
        while True:
            try:
                logger.debug("Trying to read from socket")
                with GTimeout(seconds=1):
                    data = forward_sock.recv(1024)
            except Exception as ex:
                logger.error("Forward socket read error: %s", ex)
                sleep(1)
                continue
            except GTimeout:
                logger.debug("Timeout socket read")
                self.poll()
                continue
            data_len = len(data)
            logger.debug("Read %s data from forward socket" % (data_len,))
            if data_len == 0:
                continue
            data_written = 0
            while data_written < data_len:
                try:
                    with GTimeout(seconds=1):
                        rc, bytes_written = channel.write(data[data_written:])
                except Exception as ex:
                    logger.error("Channel write error: %s", ex)
                    sleep(1)
                    continue
                except GTimeout:
                    logger.debug("Timeout writing to channel")
                    self.poll()
                    continue
                data_written += bytes_written
                if rc == LIBSSH2_ERROR_EAGAIN:
                    sleep(.2)
                    logger.debug("Data remaining %s", (data_len - data_written,))
                    # select((), ((self.client.sock,)), (), timeout=0.001)
            logger.debug("Wrote all data to channel")

    def _read_channel(self, forward_sock, channel):
        while True:
            try:
                with GTimeout(seconds=1):
                    size, data = channel.read()
            except Exception as ex:
                logger.error("Error reading from channel - %s", ex)
                sleep(1)
                continue
            except GTimeout:
                logger.debug("Timeout channel read")
                self.poll()
                continue
            logger.debug("Read %s data from channel" % (size,))
            if size == LIBSSH2_ERROR_EAGAIN:
                sleep(.2)
                continue
            try:
                with GTimeout(seconds=1):
                    forward_sock.sendall(data)
            except Exception as ex:
                logger.error(
                    "Error sending data to forward socket - %s", ex)
                sleep(.5)
                continue
            except GTimeout:
                logger.debug("Timeout writing to socket")
                self.poll()
                continue
            logger.debug("Wrote %s data to forward socket", len(data))

    def _open_channel(self, fw_host, fw_port, local_port):
        channel = self.session.direct_tcpip_ex(
            fw_host, fw_port, '127.0.0.1',
            local_port)
        while channel == LIBSSH2_ERROR_EAGAIN:
            sleep(.1)
            self.poll()
            # self.session.set_blocking(1)
            channel = self.session.direct_tcpip_ex(
                fw_host, fw_port, '127.0.0.1',
                local_port)
        self.session.set_blocking(0)
        return channel

    def _open_channel_retries(self, fw_host, fw_port, local_port,
                              wait_time=0.1):
        num_tries = 0
        while num_tries < self._retries:
            try:
                channel = self._open_channel(fw_host, fw_port, local_port)
            except Exception:
                num_tries += 1
                if num_tries > self._retries:
                    raise
                logger.error("Error opening channel to %s:%s, retries %s/%s",
                             fw_host, fw_port, num_tries, self._retries)
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
        if sock is None:
            return
        # gevent.select.poll converts seconds to miliseconds to match python socket
        # implementation
        timeout = timeout * 1000 if timeout is not None else 100
        poller = poll()
        poller.register(sock, eventmask=events)
        logger.debug("Polling socket with timeout %s", timeout)
        poller.poll(timeout=timeout)
