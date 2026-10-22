#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2026 Panos Kittenis.
#  Copyright (C) 2014-2026 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.

import unittest
from types import GeneratorType

from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN

from pssh.clients.native.sftp import SFTPClient


class DirectoryHandle(object):

    def __init__(self, entries=()):
        self.closed = False
        self.entries = entries

    def readdir(self):
        for entry in self.entries:
            if entry == LIBSSH2_ERROR_EAGAIN:
                yield LIBSSH2_ERROR_EAGAIN, b'', None
            else:
                yield len(entry), entry, None

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
        self.entries = (b'.', b'..', b'file.txt', b'data')

    def realpath(self, path):
        self.realpath_calls.append(path)
        return '/home/tester' if path == '.' else path

    def opendir(self, path):
        self.opendir_calls.append(path)
        handle = DirectoryHandle(self.entries)
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
        self.polls = 0

    def poll(self):
        self.polls += 1

    def _make_sftp(self):
        return self.sftp

    def eagain(self, func, *args):
        return func(*args)

    def _sftp_openfh(self, func, *args):
        return func(*args)

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

    def test_remote_path_leaves_dot_components_to_server(self):
        # A client-side normpath would turn link/.. into the cwd even when
        # link points elsewhere on the server.
        self.assertEqual(
            self.client._remote_path('link/../file'),
            '/home/tester/link/../file')
        self.assertEqual(
            self.client._remote_path('/var/data/../log'), '/var/data/../log')
        self.assertEqual(self.client._remote_path(''), '/home/tester')

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

    def test_listdir_filters_names_and_holds_handle_during_iteration(self):
        names = self.client.listdir('data')

        self.assertIsInstance(names, GeneratorType)
        self.assertEqual(self.sftp.opendir_calls, [])
        self.assertEqual(next(names), 'file.txt')
        self.assertEqual(self.sftp.opendir_calls, ['/home/tester/data'])
        self.assertFalse(self.sftp.handles[0].closed)
        self.assertEqual(list(names), ['data'])
        self.assertTrue(self.sftp.handles[0].closed)

    def test_listdir_keeps_newline_in_single_entry(self):
        self.sftp.entries = (b'one\ntwo.txt', b'other')

        self.assertEqual(
            list(self.client.listdir()), ['one\ntwo.txt', 'other'])

    def test_listdir_polls_on_eagain_instead_of_yielding_empty_name(self):
        self.sftp.entries = (
            LIBSSH2_ERROR_EAGAIN, b'file', LIBSSH2_ERROR_EAGAIN, b'other')

        self.assertEqual(list(self.client.listdir()), ['file', 'other'])
        self.assertEqual(self.ssh_client.polls, 2)

    def test_listdir_close_releases_partially_read_handle(self):
        names = self.client.listdir('data')

        self.assertEqual(next(names), 'file.txt')
        names.close()
        self.assertTrue(self.sftp.handles[0].closed)

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
                ('lstat', '/home/tester/../link'),
                ('rmdir', '/home/tester/empty'),
                ('rename', '/home/tester/old', '/home/tester/../new'),
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
                ('put', self.sftp, 'local.bin', '/home/tester/../remote.bin'),
                ('copy_file', self.sftp, 'tree',
                 '/home/tester/remote-tree', True),
                ('copy_remote_file', self.sftp,
                 '/home/tester/remote-tree', 'local-tree', True, 'ascii'),
            ],
        )


if __name__ == '__main__':
    unittest.main()
