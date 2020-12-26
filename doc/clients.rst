Clients Feature Comparison
============================

The two available client types, default native clients based on ``ssh2-python`` (``libssh2``) and clients under ``pssh.clients.ssh`` based on ``ssh-python`` (``libssh``) support different authentication mechanisms and features.

Below is a comparison of feature support for the two client types.

===============================  ====================== ======================
Feature                          ssh2-python (libssh2)  ssh-python (libssh)
===============================  ====================== ======================
Agent forwarding                  No                    Not yet implemented
Proxying/tunnelling               Yes                   No
Kerberos (GSS) authentication     Not supported         Yes
Private key file authentication   Yes                   Yes
Agent authentication              Yes                   Yes
Password authentication           Yes                   Yes
OpenSSH config parsing            Not yet implemented   Not yet implemented
ECDSA keys support                Yes                   Yes
ED25519 keys support              Yes                   Yes
Certificate authentication        Not supported         Yes
SFTP copy to/from hosts           Yes                   No
SCP functionality                 Yes                   No
Keep-alive functionality          Yes                   No
===============================  ====================== ======================

The default client offers the most features, but lacks certain authentication mechanisms like GSS-API and certificate authentication. Both client types are based on C libraries and offer similar levels of performance.

Users that need the authentication mechanisms not supported by the default client can ``from pssh.clients.ssh import ParallelSSHClient`` instead of the default client.
