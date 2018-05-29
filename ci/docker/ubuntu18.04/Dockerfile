FROM cdrx/fpm-ubuntu:18.04

RUN apt-get -y update && apt-get -y install python-setuptools python-dev libssh2-1-dev python-pip git
RUN pip install -U setuptools
RUN pip install -U pip wheel
RUN pip install cython
RUN pip install ssh2-python gevent paramiko

ENV EMBEDDED_LIB 1
ENV HAVE_AGENT_FWD 0
