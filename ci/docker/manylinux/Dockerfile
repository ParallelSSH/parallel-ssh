FROM quay.io/pypa/manylinux1_x86_64

ENV CMAKE cmake-2.8.11.1-5.4.x86_64
ENV OPENSSL openssl-1.0.2l
ENV LIBSSH2_VER agent_fwd

RUN yum install zlib-devel -y

ADD https://github.com/ParallelSSH/libssh2/archive/${LIBSSH2_VER}.tar.gz libssh2.tar.gz
ADD ${CMAKE}.rpm cmake.rpm
ADD http://www.openssl.org/source/${OPENSSL}.tar.gz ${OPENSSL}.tar.gz

RUN rpm -i cmake.rpm

# Openssl
RUN tar -xzf ${OPENSSL}.tar.gz && \
    cd ${OPENSSL} && \
    ./config --prefix=/usr --openssldir=/usr/openssl threads shared && \
    make -j4 && make install

# Libssh2
RUN tar -xzf libssh2.tar.gz && \
    mkdir -p build_libssh2 && cd build_libssh2 && \
    cmake ../libssh2-${LIBSSH2_VER} -DBUILD_SHARED_LIBS=ON -DENABLE_ZLIB_COMPRESSION=ON \
    -DENABLE_CRYPT_NONE=ON -DENABLE_MAC_NONE=ON -DCMAKE_INSTALL_PREFIX=/usr && \
    cmake --build . --config Release --target install

RUN rm -rf ${OPENSSL}* libssh2-agent_fwd build_libssh2

VOLUME /var/cache
