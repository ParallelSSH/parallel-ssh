#!/bin/bash -xe

docker_tag="parallelssh/parallelssh-manylinux"

rm -rf build dist

docker pull quay.io/pypa/manylinux2010_x86_64
docker tag quay.io/pypa/manylinux2010_x86_64 manylinux
docker run --rm -v `pwd`:/io manylinux /io/ci/travis/build-wheels.sh
ls wheelhouse/
