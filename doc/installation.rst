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

  python setup.py install

Or for developing changes:

.. code-block:: shell

  pip install -r requirements_dev.txt

