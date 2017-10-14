.. _contributing:

==============
 Contributing
==============

Thank you for considering to contribute to ``parallel-ssh``. Any and all contributions are encouragaged and most welcome.

Following these guidelines helps to communicate that you respect the time of the developers managing and developing this open source project. In return, they should reciprocate that respect in addressing your issue, assessing changes, and helping you finalize your pull requests.

There are many ways to contribute, from writing tutorials or blog posts, improving the documentation, contributing docker images for a particular task, submitting bug reports or feature requests or writing code to be incorporated into the project.

Please do not use the issue tracker for support questions. Use the `mail group`_ for that or other question/answer channels like Stack Overflow.

.. contents::
    :local:

Ground Rules
============

Please keep in mind the `Code of Conduct <https://github.com/ParallelSSH/parallel-ssh/blob/master/.github/code_of_conduct.md>`_ 
when making contributions.

Responsibilities

* Write PEP-8 compliant code of no more than 80 columns per line
* If adding new features, write an appropriate test - see existing tests for reference
* Contributions are expected to be in line with the project's stated `design and goals <http://parallel-ssh.readthedocs.io/en/latest/introduction.html#design-and-goals>`_

.. _reporting-bugs:


Reporting Bugs
==============

The best way to report an issue and to ensure a timely response is to use the
issue tracker.

1) **Create a GitHub account**.

You need to `create a GitHub account`_ to be able to create new issues
and participate in the discussion.

.. _`create a GitHub account`: https://github.com/signup/free

2) **Determine if your bug is really a bug**.

You shouldn't file a bug if you're requesting support. For that you can use
the `mail group`_.

3) **Make sure your bug hasn't already been reported**.

Search through the appropriate Issue tracker. If a bug like yours was found,
check if you have new information that could be reported to help
the developers fix the bug.

4) **Check if you're using the latest version**.

A bug could be fixed by some other improvements and fixes - it might not have an
existing report in the bug tracker. Make sure you're using the latest release.

5) **Collect information about the bug**.

To have the best chance of having a bug fixed, we need to be able to easily
reproduce the conditions that caused it. Most of the time this information
will be from a Python traceback message, though some bugs might be in design,
spelling or other errors on the documentation or code.

    A) If the error is from a Python traceback, include it in the bug report.

    B) We also need to know what platform you're running (Windows, macOS, Linux,
       etc.), the version of your Python interpreter, and the version of parallel-ssh,
       and related packages that you were running when the bug occurred.

There is also an issue template to help with creating issues.

6) **Submit the bug**.


By default `GitHub`_ will email you to let you know when new comments have
been made on your bug. In the event you've turned this feature off, you
should check back on occasion to ensure you don't miss any questions a
developer trying to fix the bug might ask.

.. _`GitHub`: https://github.com

Contributors guide to the code base
===================================

.. _versions:

Versions
========

Version numbers consists of a major version, minor version and a release number.

Versioning semantics described by
`SemVer <http://semver.org>`_ are used.

All releases are published at PyPI when a versioned tag is pushed to the
repository. All tags are version numbers, for example ``1.0.0``.

.. _git-branches:

Working on Features & Patches
=============================

.. note::

    Contributing should be as simple as possible,
    so none of these steps should be considered mandatory.

    You can even send in patches by email if that's your preferred
    work method. Any contribution you make
    is always appreciated!

    However following these steps may make maintainers life easier,
    and may mean that your changes will be accepted sooner.

Forking and setting up the repository
-------------------------------------

First you need to fork the ``parallel-ssh`` repository, a good introduction to this
is in the GitHub Guide: `Fork a Repo`_.

After you have cloned the repository you should checkout your copy
to a directory on your machine:

::

    $ git clone git@github.com:username/parallel-ssh.git

When the repository is cloned enter the directory to set up easy access
to upstream changes:

::

    $ cd parallel-ssh
    $ git remote add upstream git://github.com/ParallelSSH/parallel-ssh.git
    $ git fetch upstream

If you need to pull in new changes from upstream you should
always use the ``--rebase`` option to ``git pull``:

::

    git pull --rebase upstream master

With this option you don't clutter the history with merging
commit notes. See `Rebasing merge commits in git`_.
If you want to learn more about rebasing see the `Rebase`_
section in the GitHub guides.

If you need to work on a different branch than the one git calls ``master``, you can
fetch and checkout a remote branch like this::

    git checkout --track -b 3.0-devel origin/3.0-devel

.. _`Fork a Repo`: https://help.github.com/fork-a-repo/
.. _`Rebasing merge commits in git`:
    https://notes.envato.com/developers/rebasing-merge-commits-in-git/
.. _`Rebase`: https://help.github.com/rebase/

Virtual environments
---------------------

It is highly recommended that `virtual environments <http://docs.python-guide.org/en/latest/dev/virtualenvs/>`_ are used for development and testing. This avoids system wide installation of dependencies, which may conflict with system provided libraries and other applications.

.. code-block:: shell

   virtualenv dev_env
   source dev_env/bin/activate

Running the unit test suite
---------------------------

If you are developing, then you need to install development requirements first:

::

    $ pip install -U -r requirements_dev.txt

::

    $ nosetests

.. _contributing-pull-requests:

Creating pull requests
----------------------

When your feature/bugfix is complete you may want to submit
a pull requests so that it can be reviewed by the maintainers.

Creating pull requests is easy, and also let you track the progress
of your contribution. Read the `Pull Requests`_ section in the GitHub
Guide to learn how this is done.

You can also attach pull requests to existing issues by referencing the issue
number in the commit message, for example::

  git commit -m "Fixed <some bug> - resolves #22"

will refer to the issue #22, adding a message to the issue referencing the
commit and the PR, and automatically resolve the issue when the PR is merged. 

See `Closing issues using keywords`_ for more details.

.. _`Pull Requests`: http://help.github.com/send-pull-requests/

.. _`Closing issues using keywords`: https://help.github.com/articles/closing-issues-using-keywords/

.. _contributing-coverage:

Calculating test coverage
~~~~~~~~~~~~~~~~~~~~~~~~~

Add the ``--with-coverage`` flag to nose.

.. code-block:: shell

   nosetests --with-coverage
   coverage report -m

Total coverage is output even without the report command.

``coverage report -m`` will in addition show which lines are missing coverage.

Running the tests on all supported Python versions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All supported Python versions are tested by Travis-CI via test targets. For 
Travis-CI to run tests on a forked repository, Travis-CI integration will need
to be enabled on that repository.

Please see `Travis-CI documentation for enabling your repository <https://docs.travis-ci.com/user/getting-started/#To-get-started-with-Travis-CI>`_.

Building the documentation
--------------------------

After these dependencies are installed you should be able to
build the docs by running:

.. code-block:: shell

   (cd docs; rm -rf _build; make html)

Make sure there are no errors or warnings in the build output.
After building succeeds the documentation is available at ``_build/html``.

.. _contributing-verify:

Verifying your contribution
---------------------------

Required packages are installed by ``requirements_dev.txt`` per instructions
at `Running the unit test suite`_.

To ensure all tests are passing before committing, run the following in the
repository's root directory:

.. code-block:: shell

   nosetests

To ensure the code is PEP-8 compliant:

.. code-block:: shell

   flake8 pssh

To ensure documentation builds correctly:

.. code-block:: shell

   pip install sphinx
   (cd doc; make html)

Generated documentation will be found in ``doc/_build/html`` in the repository's
root directory.

See also `Travis-CI configuration <https://github.com/ParallelSSH/parallel-ssh/blob/master/.travis.yml>`_ for which tests are subject to CI.

.. _coding-style:

Coding Style
============

You should probably be able to pick up the coding style
from surrounding code, but it is a good idea to be aware of the
following conventions.


* All Python code must follow the `PEP-8 <https://www.python.org/dev/peps/pep-0008/>`_ guidelines.

  ``flake8`` and ``pep8`` are utilities you can use to verify that your code
  is following the conventions. 

  ``flake8`` is automatically run by the project's
  Travis-CI based integration tests and is required for builds to pass.

  ``autoflake`` may be used in conjuction with IDEs to automatically adjust code to be compliant.

* Docstrings must follow the `PEP-257 <https://www.python.org/dev/peps/pep-0257>`_ conventions.

* Docstrings for *public* API endpoints should include Sphinx docstring directives
  for inclusion in the auto-generated API documentation. For example::

    def method(self, arg):
        """Method for <..>

	:param arg: Argument for <..>
	:type arg: str

	:rtype: None
	"""

  See existing documentation strings for reference.

* Docstrings for internal functions - ones starting with ``_`` or ``__`` - 
  are not required.

* Lines should not exceed 80 columns.

* Import order

    * Python standard library (`import xxx`)
    * Python standard library (`from xxx import`)
    * Third-party packages.
    * Other modules from the current package.

    Within these sections the imports should be sorted by module name.

    Example:

    ::

        import threading
        import time

        from collections import deque
        from Queue import Queue, Empty

        from .platforms import Pidfile
        from .five import zip_longest, items, range
        from .utils.time import maybe_timedelta

* Wild-card imports must not be used (`from xxx import *`).

Release Procedure
=================

* Create new tag
* Add release notes for tag via GitHub releases

Creating a new tag can be done via the Github Releases page automatically if one does not already exist.

Auto-versioning from Git tags and revision
-------------------------------------------

The version number is automatically calculated based on, in order of 
preference:

* Git tag
* Latest git tag plus git revision short hand since tag
* Auto-generated version file for non-git installations

In order to publish a new version, just create and push a new tag.

::

    $ git tag X.Y.Z
    $ git push --tags

Releasing
---------

New git tags are automatically published to PyPi via Travis-CI deploy
functionality, subject to all tests and checks passing.

This includes documentation generating correctly for publishing to 
ReadTheDocs, style checks via ``flake8`` et al.

In addition to source code releases, binary wheels for Linux, OSX and Windows, all Python versions, are also built automatically for released tags only. Further more, system packages for the most popular Linux distributions are also built automatically and uploaded to Github Releases page for released tags only.

Publishing to PyPi and ReadTheDocs is only possible with Travis-CI build 
jobs initiated by the official GitHub project - forks 
cannot deploy to PyPi or publish documentation to ReadTheDocs.

.. _`mail group`: https://groups.google.com/forum/#!forum/parallelssh
