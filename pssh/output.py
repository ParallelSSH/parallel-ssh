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


"""Output module of ParallelSSH"""

from os import linesep

from . import logger


class HostOutputBuffers(object):
    __slots__ = ('stdout', 'stderr')

    def __init__(self, stdout, stderr):
        """
        :param stdout: Stdout data
        :type stdout: :py:class:`BufferData`
        :param stderr: Stderr data
        :type stderr: :py:class:`BufferData`
        """
        self.stdout = stdout
        self.stderr = stderr


class BufferData(object):
    __slots__ = ('reader', 'rw_buffer')

    def __init__(self, reader, rw_buffer):
        """
        :param reader: Greenlet reading data from channel and writing to rw_buffer
        :type reader: :py:class:`gevent.Greenlet`
        :param rw_bufffer: Read/write buffer
        :type rw_buffer: :py:class:`pssh.clients.reader.ConcurrentRWBuffer`
        """
        self.reader = reader
        self.rw_buffer = rw_buffer


class HostOutput(object):
    """Host output"""

    __slots__ = ('host', 'channel', 'stdin',
                 'client', 'exception', 'encoding', 'read_timeout',
                 'buffers',
                 )

    def __init__(self, host, channel, stdin,
                 client, exception=None, encoding='utf-8', read_timeout=None,
                 buffers=None):
        """
        :param host: Host name output is for
        :type host: str
        :param channel: SSH channel used for command execution
        :type channel: :py:class:`socket.socket` compatible object
        :param stdin: Standard input buffer
        :type stdin: :py:func:`file`-like object
        :param client: `SSHClient` output is coming from.
        :type client: :py:class:`pssh.clients.base.single.BaseSSHClient`
        :param exception: Exception from host if any
        :type exception: :py:class:`Exception` or ``None``
        :param read_timeout: Timeout in seconds for reading from buffers.
        :type read_timeout: float
        :param buffers: Host buffer data.
        :type buffers: :py:class:`HostOutputBuffers`
        """
        self.host = host
        self.channel = channel
        self.stdin = stdin
        self.client = client
        self.exception = exception
        self.encoding = encoding
        self.read_timeout = read_timeout
        self.buffers = buffers

    @property
    def stdout(self):
        if not self.client:
            return
        _stdout = self.client.read_output_buffer(
            self.client.read_output(self.buffers.stdout.rw_buffer, timeout=self.read_timeout),
            encoding=self.encoding)
        return _stdout

    @property
    def stderr(self):
        if not self.client:
            return
        _stderr = self.client.read_output_buffer(
            self.client.read_stderr(self.buffers.stderr.rw_buffer, timeout=self.read_timeout),
            encoding=self.encoding,
            prefix='\t[err]')
        return _stderr

    @property
    def exit_code(self):
        if not self.client:
            return
        try:
            return self.client.get_exit_status(self.channel)
        except Exception as ex:
            logger.error("Error getting exit status - %s", ex)

    def __repr__(self):
        return "\thost={host}{linesep}" \
            "\texit_code={exit_code}{linesep}" \
            "\tchannel={channel}{linesep}" \
            "\texception={exception}{linesep}" \
            "\tencoding={encoding}{linesep}" \
            "\tread_timeout={read_timeout}".format(
                host=self.host, channel=self.channel,
                exception=self.exception, linesep=linesep,
                exit_code=self.exit_code, encoding=self.encoding, read_timeout=self.read_timeout,
            )

    def __str__(self):
        return self.__repr__()
