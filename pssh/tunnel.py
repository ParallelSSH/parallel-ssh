from threading import Thread, Event
import logging

from gevent import socket, spawn, joinall, get_hub

from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from .ssh2_client import SSHClient
from .native._ssh2 import wait_select
from .constants import DEFAULT_RETRIES, RETRY_DELAY


logger = logging.getLogger(__name__)


class Tunnel(Thread):

    def __init__(self, host, fw_host, fw_port, user=None,
                 password=None, port=None, pkey=None,
                 num_retries=DEFAULT_RETRIES,
                 retry_delay=RETRY_DELAY,
                 allow_agent=True, timeout=None, listen_port=0):
        Thread.__init__(self)
        self.client = None
        self.session = None
        self.socket = None
        self.listen_port = listen_port
        self.fw_host = fw_host
        self.fw_port = fw_port if fw_port else 22
        self.channel = None
        self.forward_sock = None
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.pkey = pkey
        self.num_retries = num_retries
        self.retry_delay = retry_delay
        self.allow_agent = allow_agent
        self.timeout = timeout
        self.tunnel_open = Event()

    def _read_forward_sock(self):
        while True:
            logger.debug("Waiting on forward socket read")
            data = self.forward_sock.recv(1024)
            data_len = len(data)
            if data_len == 0:
                logger.error("Client disconnected")
                return
            data_written = 0
            rc = self.channel.write(data)
            while data_written < data_len:
                if rc == LIBSSH2_ERROR_EAGAIN:
                    logger.debug("Waiting on channel write")
                    wait_select(self.channel.session)
                    continue
                elif rc < 0:
                    logger.error("Channel write error %s", rc)
                    return
                data_written += rc
                logger.debug(
                    "Wrote %s bytes from forward socket to channel", rc)
                rc = self.channel.write(data[data_written:])
            logger.debug("Total channel write size %s from %s received",
                         data_written, data_len)

    def _read_channel(self):
        while True:
            size, data = self.channel.read()
            while size == LIBSSH2_ERROR_EAGAIN or size > 0:
                if size == LIBSSH2_ERROR_EAGAIN:
                    logger.debug("Waiting on channel")
                    wait_select(self.channel.session)
                    size, data = self.channel.read()
                elif size < 0:
                    logger.error("Error reading from channel")
                    return
                while size > 0:
                    logger.debug("Read %s from channel..", size)
                    self.forward_sock.sendall(data)
                    logger.debug("Forwarded %s bytes from channel", size)
                    size, data = self.channel.read()
            if self.channel.eof():
                logger.debug("Channel closed")
                return

    def _init_tunnel_sock(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('127.0.0.1', self.listen_port))
        self.socket.listen(0)
        self.listen_port = self.socket.getsockname()[1]
        logger.debug("Tunnel listening on 127.0.0.1:%s on hub %s",
                     self.listen_port, get_hub())

    def _init_tunnel_client(self):
        self.client = SSHClient(self.host, user=self.user, port=self.port,
                                password=self.password, pkey=self.pkey,
                                num_retries=self.num_retries,
                                retry_delay=self.retry_delay,
                                allow_agent=self.allow_agent,
                                timeout=self.timeout)
        self.session = self.client.session

    def run(self):
        self._init_tunnel_client()
        self._init_tunnel_sock()
        logger.debug("Hub in run function: %s", get_hub())
        try:
            while True:
                logger.debug("Tunnel waiting for connection")
                self.tunnel_open.set()
                self.forward_sock, forward_addr = self.socket.accept()
                logger.debug("Client connected, forwarding %s:%s on"
                             " remote host to local %s",
                             self.fw_host, self.fw_port,
                             forward_addr)
                self.session.set_blocking(1)
                self.channel = self.session.direct_tcpip_ex(
                    self.fw_host, self.fw_port, '127.0.0.1', forward_addr[1])
                if self.channel is None:
                    self.forward_sock.close()
                    self.socket.close()
                    raise Exception("Could not establish channel to %s:%s",
                                    self.fw_host, self.fw_port)
                self.session.set_blocking(0)
                source = spawn(self._read_forward_sock)
                dest = spawn(self._read_channel)
                joinall((source, dest))
                self.channel.close()
                self.forward_sock.close()
        finally:
            if not self.socket.closed:
                self.socket.close()
