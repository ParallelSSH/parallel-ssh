#!/bin/bash -xe

# Compile wheels
for PYBIN in `ls -1d /opt/python/cp*/bin`; do
    "${PYBIN}/pip" install -r /io/requirements.txt
    "${PYBIN}/pip" wheel --no-deps /io/ -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in wheelhouse/*.whl; do
    auditwheel repair "$whl" -w /io/wheelhouse/
done

# Install packages and test
for PYBIN in `ls -1d /opt/python/cp*/bin`; do
    "${PYBIN}/pip" install parallel-ssh --no-index -f /io/wheelhouse
    (cd "$HOME"; "${PYBIN}/python" -c 'import pssh.native._ssh2')
done
