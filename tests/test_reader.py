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

import unittest

from random import random, randint, randrange
from string import ascii_letters

from gevent.queue import Queue
from gevent import spawn, sleep
from pssh.clients.reader import ConcurrentRWBuffer


class TestReaderBuffer(unittest.TestCase):

    def setUp(self):
        self.buffer = ConcurrentRWBuffer()
        self.data = b'test'

    def test_write(self):
        self.buffer.write(self.data)
        data = self.buffer.read()
        self.assertEqual(data, self.data)

    def test_multi_write_read(self):
        written_data = self.data
        self.buffer.write(self.data)
        more_data = b"more data"
        written_data += more_data
        self.buffer.write(more_data)
        data = self.buffer.read()
        self.assertEqual(data, written_data)
        new_write_data = b"yet more data"
        self.buffer.write(new_write_data)
        data = self.buffer.read()
        self.assertEqual(data, new_write_data)
        new_write_data = b"even more data"
        self.buffer.write(new_write_data)
        data = self.buffer.read()
        self.assertEqual(data, new_write_data)

    def test_concurrent_rw(self):
        written_data = Queue()
        def _writer(_buffer):
            while True:
                data = b"".join([ascii_letters[m].encode() for m in [randrange(0, 8) for _ in range(8)]])
                _buffer.write(data)
                written_data.put(data)
                sleep(0.2)
        writer = spawn(_writer, self.buffer)
        writer.start()
        sleep(0.5)
        data = self.buffer.read()
        _data = b""
        while written_data.qsize() !=0 :
            _data += written_data.get()
        self.assertEqual(data, _data)
        sleep(0.5)
        data = self.buffer.read()
        _data = b""
        while written_data.qsize() !=0 :
            _data += written_data.get()
        self.assertEqual(data, _data)
        writer.kill()
        writer.get()

    def test_non_cur_write(self):
        data = b"asdf"
        self.buffer.write(data)
        self.buffer._buffer.seek(0)
        self.buffer.write(data)
        self.assertEqual(self.buffer.read(), data + data)
