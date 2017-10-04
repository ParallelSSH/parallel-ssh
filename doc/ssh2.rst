Clients Feature Comparison
============================

For the ``ssh2-python`` (``libssh2``) based clients, not all features supported by the paramiko based clients are currently supported by the underlying library or implemented in ``parallel-ssh``.

Below is a comparison of feature support for the two client types.

===============================  =========  ======================
Feature                          paramiko   ssh2-python (libssh2)
===============================  =========  ======================
Agent forwarding                  Yes       Not supported
Proxying/tunnelling               Yes       Not yet implemented
Kerberos (GSS) authentication     Yes       Not supported
Per-channel timeout setting       Yes       Not supported
Public key from memory            Yes       Not yet implemented
SFTP copy to/from hosts           Yes       Yes
Agent authentication              Yes       Yes
Private key file authentication   Yes       Yes
Password authentication           Yes       Yes
Session timeout setting           Yes       Yes
Per-channel timeout setting       Yes       Not supported
Programmatic SSH agent            Yes       Not supported
OpenSSH config parsing            Yes       Not yet implemented
===============================  =========  ======================

If any of missing features are required for a use case, then the paramiko based clients should be used instead. In all other cases the ``ssh2-python`` based clients offer significantly greater performance at less overhead and are preferred.
