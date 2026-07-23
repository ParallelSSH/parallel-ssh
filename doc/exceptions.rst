Exceptions
==========

Exceptions initialized with a printf-style message and its values have a
human-readable string representation while retaining the original values in
``args``. For example::

    error = AuthenticationError("Authentication failed for %s", "host.example.com")
    print(error)
    # Authentication failed for host.example.com

.. automodule:: pssh.exceptions
    :members:
    :undoc-members:
    :member-order: groupwise
