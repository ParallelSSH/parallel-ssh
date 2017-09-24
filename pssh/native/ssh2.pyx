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
# from cython.parallel import parallel, prange, threadid
from libc.stdlib cimport malloc, free
# from openmp cimport omp_lock_t, omp_init_lock, omp_set_lock, omp_unset_lock, \
#     omp_destroy_lock

from gevent.select import select

from ssh2.c_ssh2 cimport LIBSSH2_CHANNEL, LIBSSH2_SESSION_BLOCK_INBOUND, \
    LIBSSH2_SESSION_BLOCK_OUTBOUND, LIBSSH2_SESSION, \
    libssh2_session_block_directions, libssh2_channel_open_session
from ssh2.session cimport Session
from ssh2.channel cimport PyChannel
# from ssh2.agent cimport auth_identity, clear_agent, agent_auth, \
#     init_connect_agent
# from ssh2.utils cimport to_bytes


# def p_open_session(list sockets not None, list sessions not None):
#     cdef int _sock
#     cdef LIBSSH2_SESSION *c_session
#     cdef Session session
#     cdef Py_ssize_t i
#     cdef LIBSSH2_CHANNEL *chan
#     cdef list channels
#     cdef Py_ssize_t num_sessions = len(sessions)
#     cdef int *c_sockets = <int *>malloc(num_sessions * sizeof(int))
#     cdef LIBSSH2_SESSION **c_sessions = <LIBSSH2_SESSION **>malloc((
#         num_sessions) * sizeof(LIBSSH2_SESSION *))
#     cdef LIBSSH2_CHANNEL **c_channels = <LIBSSH2_CHANNEL **>malloc(
#         num_sessions * sizeof(LIBSSH2_CHANNEL *))
#     cdef omp_lock_t lock
#     # omp_init_lock(&lock)

#     if c_channels is NULL or c_sockets is NULL or c_channels is NULL:
#         raise MemoryError

#     for i in range(num_sessions):
#         sock = sockets[i]
#         session = sessions[i]
#         c_session = session._session
#         c_sessions[i] = c_session
#         _sock = PyObject_AsFileDescriptor(sock)
#         c_sockets[i] = _sock

#     for i in prange(num_sessions, nogil=True):
#         c_session = c_sessions[i]
#         _sock = c_sockets[i]
#         chan = _open_session(_sock, c_session)
#         # omp_set_lock(&lock)
#         c_channels[i] = chan
#         # omp_unset_lock(&lock)
#         # c_sessions[i] = c_session
#     free(c_sessions)
#     free(c_sockets)
#     channels = [PyChannel(c_channels[i], sessions[i])
#                 for i in range(num_sessions)]
#     free(c_channels)
#     # omp_destroy_lock(&lock)
#     return channels


cdef LIBSSH2_CHANNEL * _open_session(int _sock, LIBSSH2_SESSION * _session) nogil:
    cdef LIBSSH2_CHANNEL *chan
    chan = libssh2_channel_open_session(_session)
    while chan is NULL:
        with gil:
            _wait_select(_sock, _session)
        chan = libssh2_channel_open_session(_session)
    return chan


def open_session(_socket not None, Session session):
    cdef LIBSSH2_SESSION *_session = session._session
    cdef LIBSSH2_CHANNEL *chan
    cdef int _sock = PyObject_AsFileDescriptor(_socket)
    chan = _open_session(_sock, _session)
    return PyChannel(chan, session)


cdef int _wait_select(int _socket, LIBSSH2_SESSION *_session) except -1:
    cdef int directions = libssh2_session_block_directions(
        _session)
    cdef tuple readfds, writefds
    if directions == 0:
        return 0
    readfds = (_socket,) \
        if (directions & LIBSSH2_SESSION_BLOCK_INBOUND) else ()
    writefds = (_socket,) \
        if (directions & LIBSSH2_SESSION_BLOCK_OUTBOUND) else ()
    select(readfds, writefds, ())


def wait_select(_socket not None, Session session):
    cdef LIBSSH2_SESSION *_session = session._session
    cdef int _sock = PyObject_AsFileDescriptor(_socket)
    _wait_select(_sock, _session)


# def p_init(list sessions not None, list usernames not None, list sockets not None):
#     """Parallel session handshake and authentication"""
#     cdef bytes p_username
#     cdef char *c_username
#     cdef Py_ssize_t i
#     cdef LIBSSH2_SESSION *c_session
#     cdef Session session
#     cdef LIBSSH2_AGENT *agent = NULL
#     cdef int _sock

#     cdef Py_ssize_t num_sessions = len(sessions)
#     cdef list session_range = [i for i in range(num_sessions)]
#     cdef list p_usernames = [_ for _ in session_range]
#     cdef LIBSSH2_SESSION **c_sessions
#     cdef LIBSSH2_AGENT **agents
#     cdef char **c_usernames
#     cdef int *c_sockets

#     with nogil:
#         c_sessions = <LIBSSH2_SESSION **>malloc((
#             num_sessions) * sizeof(LIBSSH2_SESSION *))
#         agents = <LIBSSH2_AGENT **>malloc((
#             num_sessions) * sizeof(LIBSSH2_AGENT *))
#         c_usernames = <char **>malloc((num_sessions) * sizeof(char *))
#         c_sockets = <int *>malloc((num_sessions) * sizeof(int))

#     if c_sessions is NULL or c_usernames is NULL or c_sockets is NULL:
#         raise MemoryError
#     for i in session_range:
#         sock = sockets[i]
#         session = sessions[i]
#         username = usernames[i]
#         c_session = session._session
#         c_sessions[i] = c_session
#         p_username = to_bytes(username)
#         p_usernames[i] = p_username
#         c_username = p_username
#         c_usernames[i] = c_username
#         _sock = PyObject_AsFileDescriptor(sock)
#         c_sockets[i] = _sock
#     for i in prange(num_sessions, nogil=True):
#         c_session = c_sessions[i]
#         _sock = c_sockets[i]
#         libssh2_session_handshake(c_session, _sock)
#         agent = init_connect_agent(c_session)
#         c_username = c_usernames[i]
#         agent_auth(c_username, agent)
#     free(c_sessions)
#     free(c_usernames)
#     free(agents)
#     free(c_sockets)
