# This file is part of parallel-ssh.

# Copyright (C) 2014-2018 Panos Kittenis.

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

"""Cython functions for interfacing directly with ssh2-python's C-API"""

from libc.stdlib cimport malloc, free
from libc.stdio cimport fopen, fclose, fwrite, fread, FILE

from gevent.select import select

from ssh2.c_ssh2 cimport LIBSSH2_CHANNEL, LIBSSH2_SESSION_BLOCK_INBOUND, \
    LIBSSH2_SESSION_BLOCK_OUTBOUND, LIBSSH2_SESSION, \
    libssh2_session_block_directions, \
    LIBSSH2_CHANNEL_WINDOW_DEFAULT, LIBSSH2_ERROR_EAGAIN
from ssh2.c_sftp cimport libssh2_sftp_read, libssh2_sftp_write, \
    LIBSSH2_SFTP_HANDLE
from ssh2.session cimport Session
from ssh2.sftp_handle cimport SFTPHandle
from ssh2.exceptions import SFTPIOError
from ssh2.utils cimport to_bytes

from ..exceptions import SessionError, Timeout


cdef bytes LINESEP = b'\n'


def _read_output(Session session, read_func, timeout=None):
    cdef Py_ssize_t _size
    cdef bytes _data
    cdef bytes remainder = b""
    cdef Py_ssize_t remainder_len = 0
    cdef LIBSSH2_SESSION *_session = session._session
    cdef int _sock = session._sock
    cdef size_t _pos = 0
    cdef Py_ssize_t linesep
    _size, _data = read_func()
    while _size == LIBSSH2_ERROR_EAGAIN or _size > 0:
        if _size == LIBSSH2_ERROR_EAGAIN:
            _wait_select(_sock, _session, timeout)
            _size, _data = read_func()
            if timeout is not None and _size == LIBSSH2_ERROR_EAGAIN:
                raise Timeout
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


def sftp_put(Session session, SFTPHandle handle,
             local_file, size_t buffer_maxlen=LIBSSH2_CHANNEL_WINDOW_DEFAULT):
    """Native function for reading from SFTP and writing to local file"""
    cdef bytes b_local_file = to_bytes(local_file)
    cdef char *_local_file = b_local_file
    cdef FILE *local_fh
    cdef int rc
    cdef int nread
    cdef char *cbuf
    cdef char *ptr
    cdef LIBSSH2_SFTP_HANDLE *_handle = handle._handle
    cdef LIBSSH2_SESSION *_session = session._session
    cdef int _sock = session._sock

    with nogil:
        local_fh = fopen(_local_file, 'rb')
        if local_fh is NULL:
            with gil:
                raise OSError
        cbuf = <char *>malloc(sizeof(char) * buffer_maxlen)
        if cbuf is NULL:
            with gil:
                raise MemoryError
        try:
            nread = fread(cbuf, 1, buffer_maxlen, local_fh)
            if nread < 0:
                with gil:
                    raise IOError
            while nread > 0:
                ptr = cbuf
                rc = libssh2_sftp_write(_handle, ptr, nread)
                while rc > 0 or rc == LIBSSH2_ERROR_EAGAIN:
                    if rc == LIBSSH2_ERROR_EAGAIN:
                        with gil:
                            _wait_select(_sock, _session, None)
                    else:
                        ptr += rc
                        nread -= rc
                    rc = libssh2_sftp_write(_handle, ptr, nread)
                if rc < 0:
                    with gil:
                        raise SFTPIOError(rc)
                nread = fread(cbuf, 1, buffer_maxlen, local_fh)
        finally:
            free(cbuf)
            fclose(local_fh)


def sftp_get(Session session, SFTPHandle handle,
             local_file, size_t buffer_maxlen=LIBSSH2_CHANNEL_WINDOW_DEFAULT):
    """Native function for reading from local file and writing to SFTP"""
    cdef bytes b_local_file = to_bytes(local_file)
    cdef char *_local_file = b_local_file
    cdef FILE *local_fh
    cdef int rc
    cdef char *cbuf
    cdef LIBSSH2_SFTP_HANDLE *_handle = handle._handle
    cdef LIBSSH2_SESSION *_session = session._session
    cdef int _sock = session._sock

    with nogil:
        local_fh = fopen(_local_file, 'wb')
        if local_fh is NULL:
            with gil:
                raise OSError
        cbuf = <char *>malloc(sizeof(char) * buffer_maxlen)
        if cbuf is NULL:
            with gil:
                raise MemoryError
        try:
            rc = libssh2_sftp_read(_handle, cbuf, buffer_maxlen)
            while rc > 0 or rc == LIBSSH2_ERROR_EAGAIN:
                if rc == LIBSSH2_ERROR_EAGAIN:
                    with gil:
                        _wait_select(_sock, _session, None)
                elif fwrite(cbuf, 1, rc, local_fh) < 0:
                    with gil:
                        raise IOError
                rc = libssh2_sftp_read(_handle, cbuf, buffer_maxlen)
        finally:
            free(cbuf)
            fclose(local_fh)
    if rc < 0 and rc != LIBSSH2_ERROR_EAGAIN:
        raise SFTPIOError(rc)


cdef int _wait_select(int _socket, LIBSSH2_SESSION *_session,
                      timeout) except -1:
    cdef int directions = libssh2_session_block_directions(
        _session)
    cdef tuple readfds, writefds
    if directions == 0:
        return 0
    readfds = (_socket,) \
        if (directions & LIBSSH2_SESSION_BLOCK_INBOUND) else ()
    writefds = (_socket,) \
        if (directions & LIBSSH2_SESSION_BLOCK_OUTBOUND) else ()
    select(readfds, writefds, (), timeout=timeout)


def wait_select(Session session, timeout=None):
    cdef LIBSSH2_SESSION *_session = session._session
    cdef int _sock = session._sock
    _wait_select(_sock, _session, timeout)
