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

try:
    from io import BytesIO
except ImportError:
    from cStringIO import StringIO as BytesIO
from gevent.lock import RLock


class ConcurrentRWBuffer(object):

    def __init__(self):
        self._buffer = BytesIO()
        self._read_pos = 0
        self._write_pos = 0
        self._lock = RLock()

    def write(self, data):
        with self._lock:
            if not self._buffer.tell() == self._write_pos:
                self._buffer.seek(self._write_pos)
            self._write_pos += self._buffer.write(data)

    def read(self):
        with self._lock:
            if not self._buffer.tell() == self._read_pos:
                self._buffer.seek(self._read_pos)
            data = self._buffer.read()
            self._read_pos += len(data)
        return data
