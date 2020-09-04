Clients Feature Comparison
============================

For the ``ssh2-python`` (``libssh2``) based clients, not all features supported by the paramiko based clients are currently supported by the underlying library or implemented in ``parallel-ssh``.

Below is a comparison of feature support for the two client types.

===============================  ====================== ===============================================================================
Feature                          ssh2-python (libssh2)  Notes
===============================  ====================== ===============================================================================
Agent forwarding                  No                     Not yet in a libssh2 release.
Proxying/tunnelling               Yes                    Current implementation has low performance - establishes connections serially
Kerberos (GSS) authentication     Not supported
Private key file authentication   Yes                    
Agent authentication              Yes
Password authentication           Yes
SFTP copy to/from hosts           Yes
Session timeout setting           Yes
Per-channel timeout setting       Yes
Programmatic SSH agent            Not supported
OpenSSH config parsing            Not yet implemented
ECDSA keys support                Yes
ED25519 keys support              Yes
Certificate authentication        Not supported
SCP functionality                 Yes
Keep-alive functionality          Yes                     As of ``1.9.0``
===============================  ====================== ===============================================================================

If any of missing features are required for a use case, then the paramiko based clients should be used instead. Note there are several breaking bugs and low performance in some paramiko functionality, mileage may vary.

In all other cases the ``ssh2-python`` based clients offer significantly greater performance at less overhead and are preferred.
