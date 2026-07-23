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


"""Exceptions raised by parallel-ssh classes."""


class _PSSHError(Exception):
    """Base class for exceptions with printf-style message arguments."""

    def __str__(self):
        if len(self.args) < 2 or not isinstance(self.args[0], str):
            return super().__str__()
        try:
            return self.args[0] % self.args[1:]
        except (KeyError, TypeError, ValueError):
            return super().__str__()


class NoIPv6AddressFoundError(_PSSHError):
    """Raised when an IPV6 only address was requested but none are
     available for a host.

     This exception is raised instead of UnknownHostError
     in the case where only IPV4 addresses are available via DNS for a host,
     or an IPV4 address was provided but IPV6 only was requested.
     """


class UnknownHostError(_PSSHError):
    """Raised when a host is unknown (dns failure)"""
    pass


UnknownHostException = UnknownHostError
ConnectionError = ConnectionError
ConnectionErrorException = ConnectionError


class AuthenticationError(_PSSHError):
    """Raised on authentication error (user/password/ssh key error)"""
    pass


AuthenticationException = AuthenticationError


class SSHError(_PSSHError):
    """Raised on error authenticating with SSH server"""
    pass


SSHException = SSHError


class HostArgumentError(_PSSHError):
    """Raised on errors with per-host arguments to parallel functions"""
    pass


HostArgumentException = HostArgumentError


class SessionError(_PSSHError):
    """Raised on errors establishing SSH session"""
    pass


class SFTPError(_PSSHError):
    """Raised on SFTP errors"""
    pass


class SFTPIOError(SFTPError):
    """Raised on SFTP IO errors"""
    pass


class ProxyError(_PSSHError):
    """Raised on proxy errors"""


class Timeout(_PSSHError):
    """Raised on timeout requested and reached"""


class SCPError(_PSSHError):
    """Raised on errors copying file via SCP"""


class PKeyFileError(_PSSHError):
    """Raised on errors finding private key file"""


class ShellError(_PSSHError):
    """Raised on errors running command on interactive shell"""


class HostConfigError(_PSSHError):
    """Raised on invalid host configuration"""


class InvalidAPIUseError(_PSSHError):
    """Raised on invalid use of library API"""
