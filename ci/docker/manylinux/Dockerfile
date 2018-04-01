FROM quay.io/pypa/manylinux1_x86_64

ENV CMAKE cmake-2.8.12.2-Linux-i386
ENV OPENSSL openssl-1.0.2o
ENV LIBSSH2 libssh2-1.8.0

RUN yum install zlib-devel -y

# Cmake
RUN wget --no-check-certificate https://cmake.org/files/v2.8/${CMAKE}.tar.gz && \
    tar -xzf ${CMAKE}.tar.gz && cp -af ${CMAKE}/share/* /usr/share/ && \
    cp -af ${CMAKE}/bin/* /usr/bin/

# Openssl
RUN wget --no-check-certificate http://www.openssl.org/source/${OPENSSL}.tar.gz && \
    tar -xzf ${OPENSSL}.tar.gz && \
    cd ${OPENSSL} && \
    ./config --prefix=/usr --openssldir=/usr/openssl threads shared && \
    make -j4 && make install

# Libssh2
RUN wget --no-check-certificate https://www.libssh2.org/download/${LIBSSH2}.tar.gz && \
    tar -xzf ${LIBSSH2}.tar.gz

RUN cd ${LIBSSH2} && cmake ../${LIBSSH2} -DBUILD_SHARED_LIBS=ON -DENABLE_ZLIB_COMPRESSION=ON \
    -DENABLE_CRYPT_NONE=ON -DENABLE_MAC_NONE=ON -DCMAKE_INSTALL_PREFIX=/usr \
    && cmake --build . --config Release --target install

RUN rm -rf ${CMAKE}* ${OPENSSL}* ${LIBSSH2}*
