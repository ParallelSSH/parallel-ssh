Clients Feature Comparison
============================

For the ``ssh2-python`` (``libssh2``) based clients, not all features supported by the paramiko based clients are currently supported by the underlying library or implemented in ``parallel-ssh``.

Below is a comparison of feature support for the two client types.

===============================  ============== ======================
Feature                          paramiko       ssh2-python (libssh2)
===============================  ============== ======================
Agent forwarding                  Yes           Yes (binary wheels or from source builds only)
Proxying/tunnelling               Yes           Yes
Kerberos (GSS) authentication     Yes           Not supported
Private key file authentication   Yes           Yes
Private key from memory           Yes           Not yet implemented
Agent authentication              Yes           Yes
Password authentication           Yes           Yes
SFTP copy to/from hosts           Yes           Yes
Session timeout setting           Yes           Yes
Per-channel timeout setting       Yes           Yes
Programmatic SSH agent            Yes           Not supported
OpenSSH config parsing            Yes           Not yet implemented
ECSA keys support                 Yes           Yes
SCP functionality                 Not supported Yes
===============================  ============== ======================

If any of missing features are required for a use case, then the paramiko based clients should be used instead.

In all other cases the ``ssh2-python`` based clients offer significantly greater performance at less overhead and are preferred.
