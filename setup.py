from distutils.core import setup
from setuptools import find_packages

setup(name='parallel-ssh',
      version='0.1',
      description='Wrapper library over paramiko to allow remote execution of tasks. Supports parallel execution on multiple hosts',
      author='Panos Kittenis',
      author_email='pkittenis@gmail.com',
      packages = find_packages('.'),
      install_requires = open('requirements.txt').readlines(),
      )
