Native SFTP Client
==================

The native client can open a user-facing SFTP client that owns one reusable
SFTP channel and tracks a remote current working directory.

.. code-block:: python

    from pssh.clients import SSHClient

    client = SSHClient('localhost')
    sftp = client.open_sftp()
    sftp.chdir('/srv/uploads')
    sftp.mkdir('incoming')
    sftp.put('local.txt', 'incoming/remote.txt')
    print(sftp.listdir('incoming'))
    sftp.get('incoming/remote.txt', 'downloaded.txt')

Relative remote paths are resolved against ``sftp.getcwd()`` using POSIX path
semantics. The SFTP client is bound to its parent ``SSHClient`` connection.
This API is available for the native ``ssh2-python`` client only; the
``pssh.clients.ssh`` backend does not currently support SFTP.

.. automodule:: pssh.clients.native.sftp
    :members:
    :undoc-members:
    :member-order: groupwise
