#  This file is part of parallel-ssh.
#  Copyright (C) 2014-2026 Panos Kittenis.
#  Copyright (C) 2014-2026 parallel-ssh Contributors.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation, version 2.1.

import os
import shutil
import tempfile

from .base_ssh2_case import SSH2TestCase


class SFTPClientTest(SSH2TestCase):

    def test_cwd_directory_and_transfer_operations(self):
        remote_root = tempfile.mkdtemp(prefix='parallel-ssh-sftp-')
        local_root = tempfile.mkdtemp(prefix='parallel-ssh-local-')
        local_source = os.path.join(local_root, 'source.txt')
        local_copy = os.path.join(local_root, 'copy.txt')
        try:
            with open(local_source, 'w') as handle:
                handle.write('parallel-ssh')
            sftp = self.client.open_sftp()
            self.assertTrue(sftp.getcwd().startswith('/'))
            sftp.chdir(remote_root)
            self.assertEqual(sftp.getcwd(), os.path.realpath(remote_root))
            sftp.mkdir('nested')
            self.assertIn('nested', sftp.listdir('.'))
            sftp.put(local_source, 'nested/remote.txt')
            self.assertIn('remote.txt', sftp.listdir('nested'))
            sftp.get('nested/remote.txt', local_copy)
            with open(local_copy) as handle:
                self.assertEqual(handle.read(), 'parallel-ssh')
            sftp.rename('nested/remote.txt', 'nested/renamed.txt')
            sftp.remove('nested/renamed.txt')
            sftp.rmdir('nested')
            self.assertNotIn('nested', sftp.listdir('.'))
        finally:
            shutil.rmtree(remote_root, ignore_errors=True)
            shutil.rmtree(local_root, ignore_errors=True)
