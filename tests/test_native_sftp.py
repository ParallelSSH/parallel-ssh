#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2026 Panos Kittenis.
#  Copyright (C) 2014-2026 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.

import unittest

from pssh.clients.native.sftp import SFTPClient


class DirectoryHandle(object):

    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True


class SFTP(object):

    def __init__(self):
        self.realpath_calls = []
        self.opendir_calls = []
        self.handles = []
        self.calls = []

    def realpath(self, path):
        self.realpath_calls.append(path)
        return '/home/tester' if path == '.' else path

    def opendir(self, path):
        self.opendir_calls.append(path)
        handle = DirectoryHandle()
        self.handles.append(handle)
        return handle

    def stat(self, path):
        self.calls.append(('stat', path))
        return 'stat-result'

    def lstat(self, path):
        self.calls.append(('lstat', path))
        return 'lstat-result'

    def rmdir(self, path):
        self.calls.append(('rmdir', path))
        return 0

    def rename(self, source, destination):
        self.calls.append(('rename', source, destination))
        return 0

    def unlink(self, path):
        self.calls.append(('unlink', path))
        return 0


class SSHClient(object):

    def __init__(self, sftp):
        self.sftp = sftp

    def _make_sftp(self):
        return self.sftp

    def eagain(self, func, *args):
        return func(*args)

    def _sftp_openfh(self, func, *args):
        return func(*args)

    def _sftp_readdir(self, _handle):
        return iter((b'.', b'..', b'file.txt', b'data'))

    def mkdir(self, sftp, path):
        self.calls = getattr(self, 'calls', [])
        self.calls.append(('mkdir', sftp, path))

    def sftp_get(self, sftp, remote_file, local_file):
        self.calls = getattr(self, 'calls', [])
        self.calls.append(('get', sftp, remote_file, local_file))

    def sftp_put(self, sftp, local_file, remote_file):
        self.calls = getattr(self, 'calls', [])
        self.calls.append(('put', sftp, local_file, remote_file))

    def copy_file(self, local_file, remote_file, recurse=False, sftp=None):
        self.calls = getattr(self, 'calls', [])
        self.calls.append(
            ('copy_file', sftp, local_file, remote_file, recurse))

    def copy_remote_file(self, remote_file, local_file, recurse=False,
                         sftp=None, encoding='utf-8'):
        self.calls = getattr(self, 'calls', [])
        self.calls.append(
            ('copy_remote_file', sftp, remote_file, local_file,
             recurse, encoding))


class NativeSFTPClientTest(unittest.TestCase):

    def setUp(self):
        self.sftp = SFTP()
        self.ssh_client = SSHClient(self.sftp)
        self.client = SFTPClient(self.ssh_client)

    def test_initial_cwd_uses_server_realpath(self):
        self.assertEqual(self.client.getcwd(), '/home/tester')
        self.assertEqual(self.sftp.realpath_calls, ['.'])

    def test_remote_path_uses_posix_semantics(self):
        self.assertEqual(
            self.client._remote_path('../shared/./file'), '/home/shared/file')
        self.assertEqual(
            self.client._remote_path('/var//data/../log'), '/var/log')

    def test_chdir_canonicalizes_and_verifies_directory(self):
        cwd = self.client.chdir('data')

        self.assertEqual(cwd, '/home/tester/data')
        self.assertEqual(self.client.getcwd(), '/home/tester/data')
        self.assertEqual(self.sftp.opendir_calls, ['/home/tester/data'])
        self.assertTrue(self.sftp.handles[0].closed)

    def test_invalid_path_type_fails_before_transport(self):
        with self.assertRaises(TypeError):
            self.client.chdir(None)

        self.assertEqual(self.sftp.opendir_calls, [])

    def test_listdir_filters_navigation_entries(self):
        self.assertEqual(self.client.listdir('data'), ['file.txt', 'data'])
        self.assertEqual(self.sftp.opendir_calls, ['/home/tester/data'])

    def test_metadata_and_mutations_resolve_remote_paths(self):
        self.assertEqual(self.client.stat('file'), 'stat-result')
        self.assertEqual(self.client.lstat('../link'), 'lstat-result')
        self.client.rmdir('empty')
        self.client.rename('old', '../new')
        self.client.remove('obsolete')

        self.assertEqual(
            self.sftp.calls,
            [
                ('stat', '/home/tester/file'),
                ('lstat', '/home/link'),
                ('rmdir', '/home/tester/empty'),
                ('rename', '/home/tester/old', '/home/new'),
                ('unlink', '/home/tester/obsolete'),
            ],
        )

    def test_transfer_helpers_reuse_bound_channel_and_cwd(self):
        self.client.mkdir('new/child')
        self.client.get('remote.txt', 'local.txt')
        self.client.put('local.bin', '../remote.bin')
        self.client.copy_file('tree', 'remote-tree', recurse=True)
        self.client.copy_remote_file(
            'remote-tree', 'local-tree', recurse=True, encoding='ascii')

        self.assertEqual(
            self.ssh_client.calls,
            [
                ('mkdir', self.sftp, '/home/tester/new/child'),
                ('get', self.sftp, '/home/tester/remote.txt', 'local.txt'),
                ('put', self.sftp, 'local.bin', '/home/remote.bin'),
                ('copy_file', self.sftp, 'tree',
                 '/home/tester/remote-tree', True),
                ('copy_remote_file', self.sftp,
                 '/home/tester/remote-tree', 'local-tree', True, 'ascii'),
            ],
        )


if __name__ == '__main__':
    unittest.main()
