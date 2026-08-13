#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2026 Panos Kittenis.
#  Copyright (C) 2014-2026 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.

import posixpath


class SFTPClient(object):
    """User-facing SFTP operations bound to one native SSH client."""

    __slots__ = ('_client', '_sftp', '_cwd')

    def __init__(self, client, sftp=None):
        self._client = client
        self._sftp = client._make_sftp() if sftp is None else sftp
        self._cwd = self._canonical_path('.')

    def _canonical_path(self, path):
        return self._client.eagain(self._sftp.realpath, path)

    def _remote_path(self, path):
        if not isinstance(path, str):
            raise TypeError("Remote path must be a string.")
        if not path:
            return self._cwd
        if posixpath.isabs(path):
            return posixpath.normpath(path)
        return posixpath.normpath(posixpath.join(self._cwd, path))

    def getcwd(self):
        """Get the current remote working directory."""
        return self._cwd

    def chdir(self, path):
        """Change the current remote working directory."""
        target = self._canonical_path(self._remote_path(path))
        with self._client._sftp_openfh(self._sftp.opendir, target):
            pass
        self._cwd = target
        return self._cwd

    def listdir(self, path='.', encoding='utf-8'):
        """List names in a remote directory."""
        with self._client._sftp_openfh(
                self._sftp.opendir, self._remote_path(path)) as dir_h:
            entries = self._client._sftp_readdir(dir_h)
            names = [entry.decode(encoding) for entry in entries]
        return [name for name in names if name not in ('.', '..')]

    def stat(self, path):
        """Return attributes for a remote path, following symbolic links."""
        return self._client.eagain(self._sftp.stat, self._remote_path(path))

    def lstat(self, path):
        """Return attributes for a remote path without following links."""
        return self._client.eagain(self._sftp.lstat, self._remote_path(path))

    def mkdir(self, path):
        """Create a remote directory and missing parent directories."""
        return self._client.mkdir(self._sftp, self._remote_path(path))

    def rmdir(self, path):
        """Remove an empty remote directory."""
        return self._client.eagain(self._sftp.rmdir, self._remote_path(path))

    def rename(self, source, destination):
        """Rename a remote path."""
        return self._client.eagain(
            self._sftp.rename,
            self._remote_path(source),
            self._remote_path(destination),
        )

    def remove(self, path):
        """Remove a remote file."""
        return self._client.eagain(self._sftp.unlink, self._remote_path(path))

    unlink = remove

    def get(self, remote_file, local_file):
        """Copy one remote file to a local path."""
        return self._client.sftp_get(
            self._sftp, self._remote_path(remote_file), local_file)

    def put(self, local_file, remote_file):
        """Copy one local file to a remote path."""
        return self._client.sftp_put(
            self._sftp, local_file, self._remote_path(remote_file))

    def copy_file(self, local_file, remote_file, recurse=False):
        """Copy a local file or directory to a remote path."""
        return self._client.copy_file(
            local_file,
            self._remote_path(remote_file),
            recurse=recurse,
            sftp=self._sftp,
        )

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         encoding='utf-8'):
        """Copy a remote file or directory to a local path."""
        return self._client.copy_remote_file(
            self._remote_path(remote_file),
            local_file,
            recurse=recurse,
            sftp=self._sftp,
            encoding=encoding,
        )
