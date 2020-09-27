#!/bin/bash -xe

export PYBIN=`ls -1d /opt/python/cp*/bin | tail -2 | head -1`
$PYBIN/pip install -r /io/requirements.txt
$PYBIN/pip wheel --no-deps /io/ -w wheelhouse/
$PYBIN/pip install parallel-ssh --no-index -f /io/wheelhouse
$PYBIN/python -c "import pssh.clients"
