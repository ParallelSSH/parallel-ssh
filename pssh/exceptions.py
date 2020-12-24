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


"""Exceptions raised by parallel-ssh classes."""


class UnknownHostError(Exception):
    """Raised when a host is unknown (dns failure)"""
    pass


UnknownHostException = UnknownHostError


class ConnectionError(Exception):
    """Raised on error connecting (connection refused/timed out)"""
    pass


ConnectionErrorException = ConnectionError


class AuthenticationError(Exception):
    """Raised on authentication error (user/password/ssh key error)"""
    pass


AuthenticationException = AuthenticationError


class SSHError(Exception):
    """Raised on error authenticating with SSH server"""
    pass


SSHException = SSHError


class HostArgumentError(Exception):
    """Raised on errors with per-host arguments to parallel functions"""
    pass


HostArgumentException = HostArgumentError


class SessionError(Exception):
    """Raised on errors establishing SSH session"""
    pass


class SFTPError(Exception):
    """Raised on SFTP errors"""
    pass


class SFTPIOError(SFTPError):
    """Raised on SFTP IO errors"""
    pass


class ProxyError(Exception):
    """Raised on proxy errors"""


class Timeout(Exception):
    """Raised on timeout requested and reached"""


class SCPError(Exception):
    """Raised on errors copying file via SCP"""


class PKeyFileError(Exception):
    """Raised on errors finding private key file"""


class ShellError(Exception):
    """Raised on errors running command on interactive shell"""
