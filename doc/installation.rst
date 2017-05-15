*************
Installation
*************

Installation is handled by Python's standard `setuptools` library and `pip`.

Pip Install
------------

::

  pip install parallel-ssh

If `pip` is not available on your Python platform, `see this installation guide <http://docs.python-guide.org/en/latest/starting/installation/>`_.

Old Python Versions
---------------------

`1.1.x` and above releases will not be guaranteed to be compatible with Python `2.6`.

If you are running a deprecated Python version such as `2.6` you may need to install an older version of `parallel-ssh` that is compatible with your Python platform.

For example, to install the `1.0.0` version, run the following.

::

  pip install parallel-ssh==1.0.0

`1.0.0` is compatible with all Python versions over or equal to `2.6`, including all of the `3.x` series.

Older versions such as `0.70.x` are compatible with Python `2.5` but not the `3.x` series.

Source Code
-------------

Parallel-SSH is hosted on GitHub and the repository can be cloned with the following::

  git clone git@github.com:ParallelSSH/parallel-ssh.git

To install from source run::

  python setup.py install

Or with `pip`'s development mode which will ensure local changes are made available::

  pip install -e .

