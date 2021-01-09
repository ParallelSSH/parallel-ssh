*************
Installation
*************

Installation is handled by Python's standard ``setuptools`` library and ``pip``.

Pip Install
------------

``pip`` may need to be updated to be able to install binary wheel packages.

.. code-block:: shell

   pip install -U pip

   pip install parallel-ssh

If ``pip`` is not available on your Python platform, `see this installation guide <http://docs.python-guide.org/en/latest/starting/installation/>`_.

From Source Dependencies
-------------------------

When installing from source, dependencies must be satisfied by ``pip install -r requirements.txt`` or by system packages.

For binary packages, see `Pip Install`_.

===============    =====================
Dependency         Minimum Version
===============    =====================
``ssh2-python``    per requirements.txt
``ssh-python``     per requirements.txt
``gevent``         per requirements.txt
===============    =====================


Building from Source
----------------------

``parallel-ssh`` is hosted on GitHub and the repository can be cloned with the following

.. code-block:: shell

  git clone git@github.com:ParallelSSH/parallel-ssh.git
  cd parallel-ssh

To install from source run:

.. code-block:: shell

  pip install .

Or for developing changes:

.. code-block:: shell

  pip install -r requirements_dev.txt


Python 2
--------

As of January 1st 2021, Python 2 is no longer supported by the Python Software Foundation nor ``parallel-ssh`` - see `Sunset Python 2 <https://www.python.org/doc/sunset-python-2/>`_.

Versions of ``parallel-ssh<=2.4.0`` will still work.

Future releases are not guaranteed to be compatible or work at all with Python 2.

Versions ``>=2.5.0`` may still work, no code changes have yet been made to stop Python 2 from working, though no support is offered if they do not.

Vendors that distribute this package for Python 2 are advised to run integration tests themselves on versions ``>=2.5.0`` to confirm compatibility - no automated testing is performed on Python 2 by this project.

If your company requires Python 2 support contact the author directly at the email address on Github commits to discuss rates.
