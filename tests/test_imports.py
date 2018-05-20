import unittest


class ImportTestCase(unittest.TestCase):

    def test_regular_import(self):
        from pssh.clients.native.parallel import ParallelSSHClient
        from pssh.pssh2_client import ParallelSSHClient as Client2
        self.assertEqual(ParallelSSHClient, Client2)

    def test_deprecated_import(self):
        from pssh.pssh_client import ParallelSSHClient
        # To change to native in 2.0
        from pssh.clients.miko.parallel import ParallelSSHClient as Client2
        self.assertEqual(ParallelSSHClient, Client2)
        from pssh.clients.native.parallel import ParallelSSHClient as Nat
        self.assertNotEqual(ParallelSSHClient, Nat)

    def test_old_style_import(self):
        from pssh.pssh_client import ParallelSSHClient

    def test_paramiko_import(self):
        from pssh.clients.miko.parallel import ParallelSSHClient as ParallelMikoSSHClient
        from pssh.clients.native.parallel import ParallelSSHClient as Client2
        self.assertNotEqual(ParallelMikoSSHClient, Client2)

    def test_parallel_clients_import(self):
        from pssh.clients.native.parallel import ParallelSSHClient as Nat
        from pssh.clients.miko.parallel import ParallelSSHClient as Miko
        self.assertNotEqual(Miko, Nat)

    def test_single_client_imports(self):
        from pssh.clients.miko.single import SSHClient as Miko
        from pssh.clients.native.single import SSHClient as Nat
        self.assertNotEqual(Miko, Nat)

    def test_client_imports(self):
        import pssh.clients.miko
        import pssh.clients.native
        import pssh.clients
