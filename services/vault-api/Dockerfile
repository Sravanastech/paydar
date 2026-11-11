# syntax=docker/dockerfile:1.7
# vault-api base: SQLCipher compiled from pinned, checksum-verified source (ADR-09, F-41).
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ARG SQLCIPHER_VERSION=4.20.0
ARG SQLCIPHER_SHA256=38705f51b61ac0636a5fd064f9a77fafabc7227b2aa2513f1b14c8bb1102affc

FROM ${PYTHON_IMAGE} AS build
ARG SQLCIPHER_VERSION
ARG SQLCIPHER_SHA256
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl ca-certificates tcl libssl-dev \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl -fsSL -o sqlcipher.tgz "https://github.com/sqlcipher/sqlcipher/archive/refs/tags/v${SQLCIPHER_VERSION}.tar.gz" \
 && echo "${SQLCIPHER_SHA256}  sqlcipher.tgz" | sha256sum -c - \
 && tar xzf sqlcipher.tgz
# SQLCipher >= 4.7 uses autosetup; configure invocation follows the tag's README.
RUN cd "sqlcipher-${SQLCIPHER_VERSION}" \
 && ./configure --prefix=/opt/sqlcipher --with-tempstore=always --disable-tcl \
      CFLAGS="-DSQLITE_HAS_CODEC -DSQLITE_EXTRA_INIT=sqlcipher_extra_init -DSQLITE_EXTRA_SHUTDOWN=sqlcipher_extra_shutdown" LDFLAGS="-lcrypto" \
 && make -j"$(nproc)" && make install
COPY build-requirements.txt sqlcipher3-requirements.txt /src/
# Binding: hash-pinned backend and sdist. The sdist has no system-library mode: setup.py compiles a vendored
# sqlite3.c amalgamation. After the sdist hash is verified, the build drops that amalgamation and links the
# pinned upstream build in /opt/sqlcipher (SQLCipher 4.x installs it as libsqlite3) instead; its sqlite3.h replaces the vendored one (src includes ../vendor/sqlite3.h).
RUN pip install --no-cache-dir --require-hashes --no-deps -r build-requirements.txt \
 && pip download --no-deps --no-build-isolation --no-binary :all: --require-hashes \
      -r sqlcipher3-requirements.txt -d /dl \
 && mkdir /dl/src && tar xzf /dl/sqlcipher3-*.tar.gz -C /dl/src --strip-components=1 \
 && sed -i "s| + \['vendor/sqlite3.c'\]||; s|language='c')|libraries=['sqlite3'], language='c')|" /dl/src/setup.py \
 && ! grep -q "vendor/sqlite3.c" /dl/src/setup.py && grep -q "libraries=\['sqlite3'\]" /dl/src/setup.py \
 && cp /opt/sqlcipher/include/sqlite3.h /dl/src/vendor/sqlite3.h && rm /dl/src/vendor/sqlite3.c \
 && CFLAGS="-I/opt/sqlcipher/include" LDFLAGS="-L/opt/sqlcipher/lib -Wl,-rpath,/opt/sqlcipher/lib" \
    pip wheel --no-build-isolation --no-deps --wheel-dir /wheels /dl/src

FROM ${PYTHON_IMAGE} AS runtime
COPY --from=build /opt/sqlcipher/lib/ /opt/sqlcipher/lib/
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    echo /opt/sqlcipher/lib > /etc/ld.so.conf.d/sqlcipher.conf && ldconfig \
 && pip install --no-cache-dir --no-index --find-links /wheels sqlcipher3 \
 && groupadd -g 10001 paydar && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin paydar \
 && mkdir -p /data && chown 10001:10001 /data
USER 10001:10001
WORKDIR /data
CMD ["python", "-c", "import sqlcipher3; print('vault-api base ok')"]
