#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2025 Panos Kittenis.
#  Copyright (C) 2014-2025 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


"""Output module of ParallelSSH"""

from __future__ import annotations

from os import linesep
from typing import TYPE_CHECKING, Any, Iterator, Optional

from . import logger

if TYPE_CHECKING:
    from gevent import Greenlet
    from .clients.base.single import BaseSSHClient
    from .clients.reader import ConcurrentRWBuffer


class HostOutputBuffers(object):
    __slots__ = ('stdout', 'stderr')

    def __init__(self, stdout: BufferData, stderr: BufferData) -> None:
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

    def __init__(self, reader: Greenlet, rw_buffer: ConcurrentRWBuffer) -> None:
        """
        :param reader: Greenlet reading data from channel and writing to rw_buffer
        :type reader: :py:class:`gevent.Greenlet`
        :param rw_buffer: Read/write buffer
        :type rw_buffer: :py:class:`pssh.clients.reader.ConcurrentRWBuffer`
        """
        self.reader = reader
        self.rw_buffer = rw_buffer


class HostOutput(object):
    """Host output"""

    __slots__ = ('host', 'channel', 'stdin',
                 'client', 'alias', 'exception',
                 'encoding', 'read_timeout', 'buffers',
                 'fully_qualified_command',
                 )

    def __init__(self, host: str, channel: Any, stdin: Any,
                 client: Optional[BaseSSHClient], alias: Optional[str] = None,
                 exception: Optional[BaseException] = None, encoding: str = 'utf-8',
                 read_timeout: Optional[float] = None,
                 buffers: Optional[HostOutputBuffers] = None,
                 fully_qualified_command: Optional[bytes] = None,
                 ) -> None:
        """
        :param host: Host name output is for
        :type host: str
        :param channel: SSH channel used for command execution
        :type channel: :py:class:`socket.socket` compatible object
        :param stdin: Standard input buffer
        :type stdin: :py:func:`file`-like object
        :param client: `SSHClient` output is coming from.
        :type client: :py:class:`pssh.clients.base.single.BaseSSHClient` or `None`.
        :param alias: Host alias.
        :type alias: str
        :param exception: Exception from host if any
        :type exception: :py:class:`Exception` or ``None``
        :param read_timeout: Timeout in seconds for reading from buffers.
        :type read_timeout: float
        :param buffers: Host buffer data.
        :type buffers: :py:class:`HostOutputBuffers`
        :param fully_qualified_command: The fully qualified command after any per-host argument substitution and
          including command string substitution required for executing via sudo or user-switching via 'su -c', using
          any specified shell on `run_command` *and* conversion to bytes via provided encoding.
          The fully_qualified_command is therefor a bytes object that can be saved or otherwise used anywhere bytes can
          be used without conversion.
          Use `fully_qualified_command.decode(encoding)` to decode with the encoding used for the equivalent host
          output object.
          Always `None` on `HostOutput` from interactive shells.
        :type fully_qualified_command: bytes
        """
        self.host = host
        self.channel = channel
        self.stdin = stdin
        self.client = client
        self.alias = alias
        self.exception = exception
        self.encoding = encoding
        self.read_timeout = read_timeout
        self.buffers = buffers
        self.fully_qualified_command = fully_qualified_command

    @property
    def stdout(self) -> Optional[Iterator[str]]:
        if not self.client or self.buffers is None:
            return None
        _stdout = self.client.read_output_buffer(
            self.client.read_output(self.buffers.stdout.rw_buffer, timeout=self.read_timeout),
            encoding=self.encoding)
        return _stdout

    @property
    def stderr(self) -> Optional[Iterator[str]]:
        if not self.client or self.buffers is None:
            return None
        _stderr = self.client.read_output_buffer(
            self.client.read_stderr(self.buffers.stderr.rw_buffer, timeout=self.read_timeout),
            encoding=self.encoding,
            prefix='\t[err]')
        return _stderr

    @property
    def exit_code(self) -> Optional[int]:
        if not self.client:
            return None
        try:
            return self.client.get_exit_status(self.channel)
        except Exception as ex:
            logger.error("Error getting exit status - %s", ex)
        return None

    def __repr__(self) -> str:
        return "\thost={host}{linesep}" \
            "\talias={alias}{linesep}" \
            "\texit_code={exit_code}{linesep}" \
            "\tchannel={channel}{linesep}" \
            "\texception={exception}{linesep}" \
            "\tencoding={encoding}{linesep}" \
            "\tread_timeout={read_timeout}{linesep}" \
            "\tfully_qualified_command={fully_qualified_command!r}".format(
                host=self.host, alias=self.alias, channel=self.channel,
                exception=self.exception, linesep=linesep,
                exit_code=self.exit_code, encoding=self.encoding, read_timeout=self.read_timeout,
                fully_qualified_command=self.fully_qualified_command,
            )

    def __str__(self) -> str:
        return self.__repr__()
