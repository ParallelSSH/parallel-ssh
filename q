[1mdiff --git a/tests/native/test_tunnel.py b/tests/native/test_tunnel.py[m
[1mindex a4d0f69..4f0759d 100644[m
[1m--- a/tests/native/test_tunnel.py[m
[1m+++ b/tests/native/test_tunnel.py[m
[36m@@ -23,6 +23,7 @@[m [mimport sys[m
 import string[m
 import random[m
 import time[m
[32m+[m[32mimport gc[m
 [m
 from datetime import datetime[m
 from socket import timeout as socket_timeout[m
[36m@@ -31,8 +32,8 @@[m [mfrom collections import deque[m
 from gevent import sleep, spawn, Timeout as GTimeout[m
 [m
 from pssh.config import HostConfig[m
[31m-from pssh.clients.native import SSHClient, ParallelSSHClient[m
[31m-from pssh.clients.native.tunnel import LocalForwarder, TunnelServer[m
[32m+[m[32mfrom pssh.clients.native import SSHClient, ParallelSSHClient,[m
[32m+[m[32mfrom pssh.clients.native.tunnel import LocalForwarder, TunnelServer, FORWARDER[m
 from pssh.exceptions import UnknownHostException, \[m
     AuthenticationException, ConnectionErrorException, SessionError, \[m
     HostArgumentException, SFTPError, SFTPIOError, Timeout, SCPError, \[m
[36m@@ -95,6 +96,36 @@[m [mclass TunnelTest(unittest.TestCase):[m
             self.assertEqual(self.port, client.port)[m
         finally:[m
             remote_server.stop()[m
[32m+[m[41m    [m
[32m+[m[32m    # The purpose of this test is to exercise[m[41m [m
[32m+[m[32m    # https://github.com/ParallelSSH/parallel-ssh/issues/304[m[41m [m
[32m+[m[32m    def test_tunnel_server_reconn(self):[m
[32m+[m[32m        remote_host = '127.0.0.8'[m
[32m+[m[32m        remote_server = OpenSSHServer(listen_ip=remote_host, port=self.port)[m
[32m+[m[32m        remote_server.start_server()[m
[32m+[m
[32m+[m[32m        reconn_n = 20       # Number of reconnect attempts[m
[32m+[m[32m        reconn_delay = 1    # Number of seconds to delay betwen reconnects[m
[32m+[m[32m        try:[m
[32m+[m[32m            for _ in range(reconn_n):[m
[32m+[m[32m                client = SSHClient([m
[32m+[m[32m                    remote_host, port=self.port, pkey=self.user_key,[m
[32m+[m[32m                    num_retries=1,[m
[32m+[m[32m                    proxy_host=self.proxy_host,[m
[32m+[m[32m                    proxy_pkey=self.user_key,[m
[32m+[m[32m                    proxy_port=self.proxy_port,[m
[32m+[m[32m                )[m
[32m+[m[32m                output = client.run_command(self.cmd)[m
[32m+[m[32m                _stdout = list(output.stdout)[m
[32m+[m[32m                self.assertListEqual(_stdout, [self.resp])[m
[32m+[m[32m                self.assertEqual(remote_host, client.host)[m
[32m+[m[32m                self.assertEqual(self.port, client.port)[m
[32m+[m[32m                client.disconnect()[m
[32m+[m[32m                FORWARDER._cleanup_servers()[m
[32m+[m[32m                time.sleep(reconn_delay)[m
[32m+[m[32m                gc.collect()[m
[32m+[m[32m        finally:[m
[32m+[m[32m            remote_server.stop()[m
 [m
     def test_tunnel_server_same_port(self):[m
         remote_host = '127.0.0.7'[m
