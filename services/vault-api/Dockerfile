# syntax=docker/dockerfile:1.7
# vault-api base: SQLCipher compiled from pinned, checksum-verified source (ADR-09, F-41).
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ARG SQLCIPHER_VERSION=4.20.0
ARG SQLCIPHER_SHA256=38705f51b61ac0636a5fd064f9a77fafabc7227b2aa2513f1b14c8bb1102affc
ARG SQLCIPHER3_VERSION=0.6.5

FROM ${PYTHON_IMAGE} AS build
ARG SQLCIPHER_VERSION
ARG SQLCIPHER_SHA256
ARG SQLCIPHER3_VERSION
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl ca-certificates tcl libssl-dev \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl -fsSL -o sqlcipher.tgz "https://github.com/sqlcipher/sqlcipher/archive/refs/tags/v${SQLCIPHER_VERSION}.tar.gz" \
 && echo "${SQLCIPHER_SHA256}  sqlcipher.tgz" | sha256sum -c - \
 && tar xzf sqlcipher.tgz
# SQLCipher >= 4.7 uses autosetup; configure invocation follows the tag's README.
RUN cd "sqlcipher-${SQLCIPHER_VERSION}" \
 && ./configure --prefix=/opt/sqlcipher --with-tempstore=yes --disable-tcl \
      CFLAGS="-DSQLITE_HAS_CODEC -DSQLITE_EXTRA_INIT=sqlcipher_extra_init -DSQLITE_EXTRA_SHUTDOWN=sqlcipher_extra_shutdown" LDFLAGS="-lcrypto" \
 && make -j"$(nproc)" && make install
RUN CFLAGS="-I/opt/sqlcipher/include -I/opt/sqlcipher/include/sqlcipher" LDFLAGS="-L/opt/sqlcipher/lib" \
    pip wheel --no-binary sqlcipher3 --wheel-dir /wheels "sqlcipher3==${SQLCIPHER3_VERSION}"

FROM ${PYTHON_IMAGE} AS runtime
COPY --from=build /opt/sqlcipher/lib/ /opt/sqlcipher/lib/
COPY --from=build /wheels /wheels
RUN echo /opt/sqlcipher/lib > /etc/ld.so.conf.d/sqlcipher.conf && ldconfig \
 && pip install --no-cache-dir --no-index --find-links /wheels sqlcipher3 && rm -rf /wheels \
 && groupadd -g 10001 paydar && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin paydar \
 && mkdir -p /data && chown 10001:10001 /data
USER 10001:10001
WORKDIR /data
CMD ["python", "-c", "import sqlcipher3; print('vault-api base ok')"]
