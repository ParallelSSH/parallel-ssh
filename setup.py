from distutils.core import setup
from setuptools import find_packages

setup(name='parallel-ssh',
      version='0.2',
      description='Wrapper library over paramiko to allow remote execution of tasks. Supports parallel execution on multiple hosts',
      author='Panos Kittenis',
      author_email='pkittenis@gmail.com',
      url = "https://github.com/pkittenis/parallel-ssh",
      py_modules = ['pssh'],
      install_requires = ['paramiko', 'gevent'],
      )
