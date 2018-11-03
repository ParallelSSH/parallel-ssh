# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2018 Panos Kittenis.
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

from threading import Thread, Event
import logging

from gevent import socket, spawn, joinall, get_hub, sleep
from gevent.select import select

from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from .single import SSHClient
from ...constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)


class Tunnel(Thread):
    """SSH proxy implementation with direct TCP/IP tunnels.

    Each tunnel object runs in its own thread and can open any number of
    direct tunnels to remote host:port destinations on local ports over
    the same SSH connection.

    To use, append ``(host, port)`` tuples into ``Tunnel.in_q`` and read
    listen port for tunnel connection from ``Tunnel.out_q``.

    ``Tunnel.tunnel_open`` is a *thread* event that will be set once tunnel is
    ready."""

    def __init__(self, host, in_q, out_q, user=None,
                 password=None, port=None, pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None,
                 channel_retries=5):
        """
        :param host: Remote SSH host to open tunnels with.
        :type host: str
        :param in_q: Deque for requesting new tunnel to given ``((host, port))``
        :type in_q: :py:class:`collections.deque`
        :param out_q: Deque for feeding back tunnel listening ports.
        :type out_q: :py:class:`collections.deque`
        :param user: (Optional) User to login as. Defaults to logged in user
        :type user: str
        :param password: (Optional) Password to use for login. Defaults to
          no password
        :type password: str
        :param port: (Optional) Port number to use for SSH connection. Defaults
          to ``None`` which uses SSH default (22)
        :type port: int
        :param pkey: Private key file path to use. Note that the public key file
          pair *must* also exist in the same location with name ``<pkey>.pub``
        :type pkey: str
        :param num_retries: (Optional) Number of connection and authentication
          attempts before the client gives up. Defaults to 3.
        :type num_retries: int
        :param retry_delay: Number of seconds to wait between retries. Defaults
          to :py:class:`pssh.constants.RETRY_DELAY`
        :type retry_delay: int
        :param timeout: SSH session timeout setting in seconds. This controls
          timeout setting of authenticated SSH sessions.
        :type timeout: int
        :param allow_agent: (Optional) set to False to disable connecting to
          the system's SSH agent.
        :type allow_agent: bool
        """
        Thread.__init__(self)
        self.client = None
        self.session = None
        self._sockets = []
        self.in_q = in_q
        self.out_q = out_q
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.pkey = pkey
        self.num_retries = num_retries
        self.retry_delay = retry_delay
        self.allow_agent = allow_agent
        self.timeout = timeout
        self.exception = None
        self.tunnel_open = Event()
        self._tunnels = []
        self.channel_retries = channel_retries

    def __del__(self):
        self.cleanup()

    def _read_forward_sock(self, forward_sock, channel):
        while True:
            if channel.eof():
                logger.debug("Channel closed")
                return
            try:
                data = forward_sock.recv(1024)
            except Exception:
                logger.exception("Forward socket read error:")
                sleep(1)
                continue
            data_len = len(data)
            if data_len == 0:
                continue
            data_written = 0
            while data_written < data_len:
                try:
                    rc, bytes_written = channel.write(data[data_written:])
                except Exception:
                    logger.exception("Channel write error:")
                    sleep(1)
                    continue
                data_written += bytes_written
                if rc == LIBSSH2_ERROR_EAGAIN:
                    select((), ((self.client.sock,)), (), timeout=0.001)

    def _read_channel(self, forward_sock, channel):
        while True:
            if channel.eof():
                logger.debug("Channel closed")
                return
            try:
                size, data = channel.read()
            except Exception as ex:
                logger.error("Error reading from channel - %s", ex)
                sleep(1)
                continue
            while size == LIBSSH2_ERROR_EAGAIN or size > 0:
                if size == LIBSSH2_ERROR_EAGAIN:
                    select((self.client.sock,), (), (), timeout=0.001)
                    try:
                        size, data = channel.read()
                    except Exception as ex:
                        logger.error("Error reading from channel - %s", ex)
                        sleep(1)
                        continue
                while size > 0:
                    try:
                        forward_sock.sendall(data)
                    except Exception as ex:
                        logger.error(
                            "Error sending data to forward socket - %s", ex)
                        sleep(.5)
                        continue
                    try:
                        size, data = channel.read()
                    except Exception as ex:
                        logger.error("Error reading from channel - %s", ex)
                        sleep(.5)

    def _init_tunnel_sock(self):
        tunnel_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tunnel_socket.settimeout(self.timeout)
        tunnel_socket.bind(('127.0.0.1', 0))
        tunnel_socket.listen(0)
        listen_port = tunnel_socket.getsockname()[1]
        self._sockets.append(tunnel_socket)
        return tunnel_socket, listen_port

    def _init_tunnel_client(self):
        self.client = SSHClient(self.host, user=self.user, port=self.port,
                                password=self.password, pkey=self.pkey,
                                num_retries=self.num_retries,
                                retry_delay=self.retry_delay,
                                allow_agent=self.allow_agent,
                                timeout=self.timeout,
                                _auth_thread_pool=False)
        self.session = self.client.session
        self.tunnel_open.set()

    def cleanup(self):
        for _sock in self._sockets:
            if not _sock:
                continue
            try:
                _sock.close()
            except Exception as ex:
                logger.error("Exception while closing sockets - %s", ex)
        if self.session is not None:
            self.client.disconnect()

    def _consume_q(self):
        while True:
            try:
                host, port = self.in_q.pop()
            except IndexError:
                sleep(1)
                continue
            logger.debug("Got request for tunnel to %s:%s", host, port)
            tunnel = spawn(self._start_tunnel, host, port)
            self._tunnels.append(tunnel)

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

    def _open_channel_retries(self, fw_host, fw_port, local_port,
                              wait_time=0.1):
        num_tries = 0
        while num_tries < self.channel_retries:
            try:
                channel = self._open_channel(fw_host, fw_port, local_port)
            except Exception:
                num_tries += 1
                if num_tries > self.num_retries:
                    raise
                logger.error("Error opening channel to %s:%s, retries %s/%s",
                             fw_host, fw_port, num_tries, self.num_retries)
                sleep(wait_time)
                wait_time *= 5
                continue
            return channel

    def _start_tunnel(self, fw_host, fw_port):
        try:
            listen_socket, listen_port = self._init_tunnel_sock()
        except Exception as ex:
            logger.error("Error initialising tunnel listen socket - %s", ex)
            self.exception = ex
            return
        logger.debug("Tunnel listening on 127.0.0.1:%s on hub %s",
                     listen_port, get_hub().thread_ident)
        self.out_q.append(listen_port)
        try:
            forward_sock, forward_addr = listen_socket.accept()
        except Exception as ex:
            logger.error("Error accepting connection from client - %s", ex)
            self.exception = ex
            listen_socket.close()
            return
        forward_sock.settimeout(self.timeout)
        logger.debug("Client connected, forwarding %s:%s on"
                     " remote host to %s",
                     fw_host, fw_port, forward_addr)
        local_port = forward_addr[1]
        try:
            channel = self._open_channel_retries(fw_host, fw_port, local_port)
        except Exception as ex:
            logger.exception("Could not establish channel to %s:%s:",
                             fw_host, fw_port)
            self.exception = ex
            forward_sock.close()
            listen_socket.close()
            return
        source = spawn(self._read_forward_sock, forward_sock, channel)
        dest = spawn(self._read_channel, forward_sock, channel)
        logger.debug("Waiting for read/write greenlets")
        self._wait_send_receive_lets(source, dest, channel, forward_sock)

    def _wait_send_receive_lets(self, source, dest, channel, forward_sock):
        try:
            joinall((source, dest), raise_error=True)
        except Exception as ex:
            logger.error(ex)
        finally:
            logger.debug("Closing channel and forward socket")
            channel.close()
            forward_sock.close()

    def run(self):
        """Thread run target. Starts tunnel client and waits for incoming
        tunnel connection requests from ``Tunnel.in_q``."""
        try:
            self._init_tunnel_client()
        except Exception as ex:
            # logger.error("Tunnel initilisation failed - %s", ex)
            self.exception = ex
            return
        logger.debug("Hub ID in run function: %s", get_hub().thread_ident)
        consume_let = spawn(self._consume_q)
        try:
            consume_let.get()
        except Exception as ex:
            logger.error("Tunnel thread caught exception and will exit:",
                         exc_info=1)
            self.exception = ex
        finally:
            self.cleanup()
