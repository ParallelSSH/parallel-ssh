# This file is part of parallel-ssh.

# Copyright (C) 2014-2017 Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""Functions for interfacing directly with ssh2-python's C-API"""

from cpython cimport PyObject_AsFileDescriptor

from gevent.select import select

from ssh2.c_ssh2 cimport LIBSSH2_CHANNEL, LIBSSH2_SESSION_BLOCK_INBOUND, \
    LIBSSH2_SESSION_BLOCK_OUTBOUND, LIBSSH2_SESSION, \
    libssh2_session_block_directions, libssh2_channel_open_session
from ssh2.session cimport Session
from ssh2.channel cimport Channel, PyChannel


def open_session(_socket not None, Session session):
    cdef int _sock = PyObject_AsFileDescriptor(_socket)
    cdef LIBSSH2_SESSION *_session = session._session
    cdef LIBSSH2_CHANNEL *chan
    with nogil:
        chan = libssh2_channel_open_session(_session)
        while chan is NULL:
            with gil:
                _wait_select(_sock, _session)
            chan = libssh2_channel_open_session(_session)
    return PyChannel(chan, session)


cdef _wait_select(int _socket, LIBSSH2_SESSION *_session):
    cdef int directions = libssh2_session_block_directions(
        _session)
    cdef tuple readfds, writefds
    if directions == 0:
        return 0
    readfds = (_socket,) \
        if (directions & LIBSSH2_SESSION_BLOCK_INBOUND) else ()
    writefds = (_socket,) \
        if (directions & LIBSSH2_SESSION_BLOCK_OUTBOUND) else ()
    select(readfds, writefds, (), 1)


def wait_select(_socket not None, Session session):
    cdef LIBSSH2_SESSION *_session = session._session
    cdef int _sock = PyObject_AsFileDescriptor(_socket)
    return _wait_select(_sock, _session)
