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


"""Output module of ParallelSSH"""

from os import linesep

from . import logger


class HostOutput(dict):
    """Class to hold host output"""

    __slots__ = ('host', 'cmd', 'channel', 'stdout', 'stderr', 'stdin',
                 'client', 'exception')

    def __init__(self, host, cmd, channel, stdout, stderr, stdin,
                 client, exception=None):
        """
        :param host: Host name output is for
        :type host: str
        :param cmd: Command execution object
        :type cmd: :py:class:`gevent.Greenlet`
        :param channel: SSH channel used for command execution
        :type channel: :py:class:`socket.socket` compatible object
        :param stdout: Standard output buffer
        :type stdout: generator
        :param stderr: Standard error buffer
        :type stderr: generator
        :param stdin: Standard input buffer
        :type stdin: :py:func:`file`-like object
        :param exit_code: Exit code of command
        :type exit_code: int or None
        :param exception: Exception from host if any
        :type exception: :py:class:`Exception` or ``None``
        """
        super(HostOutput, self).__init__(
            (('host', host), ('cmd', cmd), ('channel', channel),
             ('stdout', stdout), ('stderr', stderr),
             ('stdin', stdin),
             ('exception', exception)))
        self.host = host
        self.cmd = cmd
        self.channel = channel
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = stdin
        self.client = client
        self.exception = exception

    @property
    def exit_code(self):
        if not self.client:
            return
        try:
            return self.client.get_exit_status(self.channel)
        except Exception as ex:
            logger.error("Error getting exit status - %s", ex)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        dict.__setitem__(self, name, value)

    def update(self, update_dict):
        """Override of dict update function for backwards compatibility"""
        dict.update(self, update_dict)
        for key in update_dict:
            object.__setattr__(self, key, update_dict[key])

    def __repr__(self):
        return "{linesep}\thost={host}{linesep}" \
            "\texit_code={exit_code}{linesep}" \
            "\tcmd={cmd}{linesep}\tchannel={channel}{linesep}" \
            "\tstdout={stdout}{linesep}\tstderr={stderr}{linesep}" \
            "\tstdin={stdin}{linesep}" \
            "\texception={exception}{linesep}".format(
                host=self.host, cmd=self.cmd, channel=self.channel,
                stdout=self.stdout, stdin=self.stdin, stderr=self.stderr,
                exception=self.exception, linesep=linesep,
                exit_code=self.exit_code)

    def __str__(self):
        return self.__repr__()
