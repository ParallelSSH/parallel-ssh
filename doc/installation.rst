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

Old Python Versions
---------------------

``1.1.x`` and above releases are not guaranteed to be compatible with Python ``2.6``.

If you are running a deprecated Python version such as ``2.6`` you may need to install an older version of ``parallel-ssh`` that is compatible with that Python platform.

For example, to install the ``1.0.0`` version, run the following.

.. code-block:: shell

  pip install parallel-ssh==1.0.0

``1.0.0`` is compatible with all Python versions over or equal to ``2.6``, including all of the ``3.x`` series.

Older versions such as `0.70.x` are compatible with Python ``2.5`` and ``2.x`` but not the ``3.x`` series.

Dependencies
--------------

When installing from source, it is responsibility of user to satisfy dependencies. For pre-built binary wheel packages with dependencies included, see `Pip Install`_.

============ ================
Dependency   Minimum Version
============ ================
``libssh2``      ``1.6``
``gevent``       ``1.1``
``paramiko``     ``1.15.3``
============ ================


Building from Source
----------------------


``parallel-ssh`` is hosted on GitHub and the repository can be cloned with the following

.. code-block:: shell

  git clone git@github.com:ParallelSSH/parallel-ssh.git
  cd parallel-ssh

To install from source run:

.. code-block:: shell

  python setup.py install

Or with ``pip``'s development mode which will ensure local changes are made available:

.. code-block:: shell

  pip install -e .

Building System Packages
--------------------------

For convenience, a script making use of Docker is provided at `ci/docker/build-packages.sh <https://github.com/ParallelSSH/parallel-ssh/blob/master/ci/docker/build-packages.sh>`_ that will build system packages for Centos/RedHat 6/7, Ubuntu 14.04/16.04, Debian 7/8 and Fedora 22/23/24.

Note that these packages make use of system libraries that may need to be updated to be compatible with ``parallel-ssh`` - see `Dependencies`_.

.. code-block:: shell

   git clone git@github.com:ParallelSSH/parallel-ssh.git
   cd parallel-ssh
   # Checkout a tag for tagged builds - git tag; git checkout <tag>
   ./ci/docker/build-packages.sh
   ls -1tr

.. code-block:: shell

   python-parallel-ssh-1.2.0+4.ga811e69.dirty-1.el6.x86_64.rpm
   python-parallel-ssh-1.2.0+4.ga811e69.dirty-1.el7.x86_64.rpm
   python-parallel-ssh-1.2.0+4.ga811e69.dirty-1.fc22.x86_64.rpm
   python-parallel-ssh-1.2.0+4.ga811e69.dirty-1.fc23.x86_64.rpm
   python-parallel-ssh-1.2.0+4.ga811e69.dirty-1.fc24.x86_64.rpm
   python-parallel-ssh_1.2.0+4.ga811e69.dirty-debian7_amd64.deb
   python-parallel-ssh_1.2.0+4.ga811e69.dirty-debian8_amd64.deb

Specific System Package Build
_______________________________

To build for only a specific system/distribution, run the two following commands, substituting distribution with the desired one from `ci/docker <https://github.com/ParallelSSH/parallel-ssh/blob/master/ci/docker>`_. See `existing Dockerfiles <https://github.com/ParallelSSH/parallel-ssh/tree/master/ci/docker/ubuntu16.04/Dockerfile>`_ for examples on how to create system packages for other distributions.

Debian based
+++++++++++++

.. code-block:: shell

   docker build --cache-from parallelssh/ssh2-python:debian7 ci/docker/debian7 -t debian7
   docker run -v "$(pwd):/src/" debian7 --iteration debian7 -s python -t deb setup.py


RPM based
++++++++++

.. code-block:: shell

   docker build --cache-from parallelssh/ssh2-python:centos7 ci/docker/centos7 -t centos7
   docker run -v "$(pwd):/src/" centos7 --rpm-dist el7 -s python -t rpm setup.py
