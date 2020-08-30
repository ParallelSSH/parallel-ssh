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

"""Cython functions for interfacing with ssh2-python and ssh-python"""

from gevent.select import poll, POLLIN, POLLOUT
from ssh2.session import LIBSSH2_SESSION_BLOCK_INBOUND, LIBSSH2_SESSION_BLOCK_OUTBOUND
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh.session import SSH_READ_PENDING, SSH_WRITE_PENDING
from ssh.error_codes import SSH_AGAIN

from ..exceptions import Timeout
from gevent import Timeout as GTimeout


cdef bytes LINESEP = b'\n'
cdef int _LIBSSH2_ERROR_EAGAIN = LIBSSH2_ERROR_EAGAIN
cdef int _LIBSSH2_SESSION_BLOCK_INBOUND = LIBSSH2_SESSION_BLOCK_INBOUND
cdef int _LIBSSH2_SESSION_BLOCK_OUTBOUND = LIBSSH2_SESSION_BLOCK_OUTBOUND
cdef int _SSH_READ_PENDING = SSH_READ_PENDING
cdef int _SSH_WRITE_PENDING = SSH_WRITE_PENDING
cdef int _SSH_AGAIN = SSH_AGAIN
cdef int _POLLIN = POLLIN
cdef int _POLLOUT = POLLOUT


def _read_output(session, read_func, timeout=None):
    cdef Py_ssize_t _size
    cdef bytes _data
    cdef bytes remainder = b""
    cdef Py_ssize_t remainder_len = 0
    cdef size_t _pos = 0
    cdef Py_ssize_t linesep
    _size, _data = read_func()
    t = GTimeout(timeout)
    t.start()
    try:
        while _size == _LIBSSH2_ERROR_EAGAIN or _size > 0:
            if _size == _LIBSSH2_ERROR_EAGAIN:
                wait_select(session, timeout)
                _size, _data = read_func()
            while _size > 0:
                while _pos < _size:
                    linesep = _data[:_size].find(LINESEP, _pos)
                    if linesep >= 0:
                        if remainder_len > 0:
                            yield remainder + _data[_pos:linesep].rstrip()
                            remainder = b""
                            remainder_len = 0
                        else:
                            yield _data[_pos:linesep].rstrip()
                        _pos = linesep + 1
                    else:
                        remainder += _data[_pos:]
                        remainder_len = len(remainder)
                        break
                _size, _data = read_func()
                _pos = 0
        if remainder_len > 0:
            # Finished reading without finding ending linesep
            yield remainder
    except GTimeout:
        raise Timeout
    finally:
        t.close()


def wait_select(session, timeout=None):
    """Perform co-operative gevent select on ssh2 session socket.

    Blocks current greenlet only if socket has pending read or write operations
    in the appropriate direction.
    """
    cdef int events = 0
    cdef int directions = session.block_directions()
    if directions == 0:
        return 0
    _socket = session.sock
    # gevent.select.poll converts seconds to miliseconds to match python socket
    # implementation
    timeout = timeout * 1000 if timeout is not None else None
    if directions & _LIBSSH2_SESSION_BLOCK_INBOUND:
        events = _POLLIN
    if directions & _LIBSSH2_SESSION_BLOCK_OUTBOUND:
        events |= _POLLOUT
    poller = poll()
    poller.register(_socket, eventmask=events)
    poller.poll(timeout=timeout)


def wait_select_ssh(session, timeout=None):
    """ssh-python based co-operative gevent select on session socket."""
    cdef int events = 0
    cdef int directions = session.get_poll_flags()
    if directions == 0:
        return 0
    _socket = session.sock
    timeout = timeout * 1000 if timeout is not None else None
    if directions & _SSH_READ_PENDING:
        events = _POLLIN
    if directions & _SSH_WRITE_PENDING:
        events |= _POLLOUT
    poller = poll()
    poller.register(_socket, eventmask=events)
    poller.poll(timeout=timeout)


def eagain_write(write_func, data, session, timeout=None):
    """Write data with given write_func for an ssh2-python session while
    handling EAGAIN and resuming writes from last written byte on each call to
    write_func.
    """
    cdef Py_ssize_t data_len = len(data)
    cdef size_t total_written = 0
    cdef int rc
    cdef size_t bytes_written
    while total_written < data_len:
        rc, bytes_written = write_func(data[total_written:])
        total_written += bytes_written
        if rc == _LIBSSH2_ERROR_EAGAIN:
            wait_select(session, timeout=timeout)


def eagain_ssh(session, func, *args, **kwargs):
    """Run function given and handle EAGAIN for an ssh-python session"""
    timeout = kwargs.pop('timeout', None)
    cdef int ret = func(*args, **kwargs)
    while ret == _SSH_AGAIN:
        wait_select_ssh(session, timeout=timeout)
        ret = func(*args, **kwargs)
        if ret == _SSH_AGAIN and timeout is not None:
            raise Timeout
    return ret
