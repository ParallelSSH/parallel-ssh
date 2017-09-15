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
from cython.parallel import parallel, prange, threadid
from libc.stdlib cimport malloc, free
from libc.stdio cimport printf

from gevent.select import select

from ssh2.exceptions cimport AgentListIdentitiesError
from ssh2.c_ssh2 cimport LIBSSH2_CHANNEL, LIBSSH2_SESSION_BLOCK_INBOUND, \
    LIBSSH2_SESSION_BLOCK_OUTBOUND, LIBSSH2_SESSION, \
    LIBSSH2_AGENT, libssh2_session_handshake, \
    libssh2_session_block_directions, libssh2_channel_open_session, \
    libssh2_agent_userauth, libssh2_agent_list_identities, \
    libssh2_agent_publickey
from ssh2.session cimport Session, init_connect_agent
from ssh2.channel cimport Channel, PyChannel
from ssh2.agent cimport auth_identity, clear_agent
from ssh2.utils cimport to_bytes


def open_session(_socket not None, Session session):
    cdef int _sock = PyObject_AsFileDescriptor(_socket)
    cdef LIBSSH2_SESSION *_session = session._session
    cdef LIBSSH2_CHANNEL *chan
    chan = libssh2_channel_open_session(_session)
    while chan is NULL:
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


def p_init(list sessions not None, list usernames not None, list sockets not None):
    """Parallel session handshake and authentication"""
    cdef bytes p_username
    cdef char *c_username
    cdef Py_ssize_t i
    cdef LIBSSH2_SESSION *c_session
    cdef Session session
    cdef LIBSSH2_AGENT *agent = NULL
    cdef int _sock

    cdef Py_ssize_t num_sessions = len(sessions)
    cdef list p_usernames = [_ for _ in range(num_sessions)]
    cdef LIBSSH2_SESSION **c_sessions = <LIBSSH2_SESSION **>malloc((
        num_sessions) * sizeof(LIBSSH2_SESSION *))
    cdef LIBSSH2_AGENT **agents = <LIBSSH2_AGENT **>malloc((
        num_sessions) * sizeof(LIBSSH2_AGENT *))
    cdef char **c_usernames = <char **>malloc((num_sessions) * sizeof(char *))
    cdef int *c_sockets = <int *>malloc((num_sessions) * sizeof(int))

    if c_sessions is NULL or c_usernames is NULL or c_sockets is NULL:
        raise MemoryError
    for i in range(len(sessions)):
        sock = sockets[i]
        session = sessions[i]
        username = usernames[i]
        c_session = session._session
        c_sessions[i] = c_session
        p_username = to_bytes(username)
        p_usernames[i] = p_username
        c_username = p_username
        c_usernames[i] = c_username
        _sock = PyObject_AsFileDescriptor(sock)
        c_sockets[i] = _sock
    c_username = NULL
    c_session = NULL
    _sock = 0
    for i in prange(num_sessions, nogil=True):
        c_session = c_sessions[i]
        _sock = c_sockets[i]
        libssh2_session_handshake(c_session, _sock)
        agent = init_connect_agent(c_session)
        c_username = c_usernames[i]
        agent_auth(c_username, agent)
    free(c_sessions)
    free(c_usernames)
    free(agents)


cdef void agent_auth(char * _username, LIBSSH2_AGENT * agent) nogil:
    cdef libssh2_agent_publickey *identity = NULL
    cdef libssh2_agent_publickey *prev = NULL
    if libssh2_agent_list_identities(agent) != 0:
        clear_agent(agent)
        with gil:
            raise AgentListIdentitiesError(
                "Failure requesting identities from agent")
    while 1:
        auth_identity(_username, agent, &identity, prev)
        if libssh2_agent_userauth(
                agent, _username, identity) == 0:
            clear_agent(agent)
            break
        prev = identity
