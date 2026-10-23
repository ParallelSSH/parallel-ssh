Native SFTP Client
==================

The native client can open a user-facing SFTP client that owns one reusable
SFTP channel and tracks a remote current working directory.

.. code-block:: python

    from pssh.clients import SSHClient

    client = SSHClient('localhost')
    sftp = client.make_sftp_client()
    sftp.chdir('/srv/uploads')
    sftp.mkdir('incoming')
    sftp.put('local.txt', 'incoming/remote.txt')
    print(list(sftp.listdir('incoming')))
    sftp.get('incoming/remote.txt', 'downloaded.txt')

Relative remote paths are joined to ``sftp.getcwd()``; ``.`` and ``..``
components are resolved by the server. ``listdir`` returns a generator that
keeps the remote directory handle open until it is exhausted or closed. The SFTP client is bound to its parent ``SSHClient`` connection.
This API is available for the native ``ssh2-python`` client only; the
``pssh.clients.ssh`` backend does not currently support SFTP.

.. automodule:: pssh.clients.native.sftp
    :members:
    :undoc-members:
    :member-order: groupwise
