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

from io import BytesIO

from gevent.event import Event
from gevent.lock import RLock


class _Eof(Event):
    def __init__(self, unread_data):
        self._unread_data = unread_data
        Event.__init__(self)

    def set(self):
        self._unread_data.set()
        Event.set(self)


class ConcurrentRWBuffer(object):
    """Concurrent reader/writer of bytes for use from multiple greenlets.

    Supports both concurrent reading and writing.

    Iterate on buffer object to read data, yielding event loop if no data exists
    until self.eof has been set.

    Writers should call ``ConcurrentRWBuffer.eof.set()`` when finished writing data via ``write``.

    Readers can use ``read()`` to get any available data or ``None``.
    """
    __slots__ = ('_buffer', '_read_pos', '_write_pos', 'eof', '_lock', '_unread_data')

    def __init__(self):
        self._buffer = BytesIO()
        self._read_pos = 0
        self._write_pos = 0
        self._lock = RLock()
        self._unread_data = Event()
        self.eof = _Eof(self._unread_data)

    def write(self, data):
        """Write data to buffer.

        :param data: Data to write
        :type data: bytes
        """
        with self._lock:
            if not self._buffer.tell() == self._write_pos:
                self._buffer.seek(self._write_pos)
            self._write_pos += self._buffer.write(data)
            if not self._unread_data.is_set() and self._read_pos < self._write_pos:
                self._unread_data.set()

    def read(self):
        """Read available data, or return None.

        :rtype: bytes
        """
        with self._lock:
            if self._write_pos == 0 or self._read_pos == self._write_pos:
                self._unread_data.clear()
                return
            elif not self._buffer.tell() == self._read_pos:
                self._buffer.seek(self._read_pos)
            data = self._buffer.read()
            self._read_pos += len(data)
        return data

    def __iter__(self):
        while not self.eof.is_set() or self._read_pos != self._write_pos:
            data = self.read()
            if data:
                yield data
            else:
                self._unread_data.wait()
