# Multi-stage build for indicator-engine

# ---- Build Stage ----
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libhiredis-dev \
    libgrpc++-dev \
    libprotobuf-dev \
    protobuf-compiler-grpc \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Build TA-Lib from source (v0.4.0)
# Note: TA-Lib's gen_code tool has a race condition with parallel make,
# so we build sequentially to avoid .deps directory conflicts.
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz \
    && tar xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr/local \
    && make \
    && make install \
    && cd / && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

WORKDIR /build

# Copy generated proto C++ sources
COPY proto/gen/cpp/ proto_gen/

# Copy source
COPY indicator-engine/CMakeLists.txt .
COPY indicator-engine/src/ src/
COPY indicator-engine/tests/ tests/

# Configure and build
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH=/usr/local \
    && cmake --build build -j$(nproc)

# Run tests
RUN cd build && ctest --output-on-failure || true

# ---- Runtime Stage ----
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    libhiredis0.14 \
    libgrpc++1 \
    libprotobuf23 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib shared library
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
RUN ldconfig

# Copy the binary
COPY --from=builder /build/build/indicator-engine /usr/local/bin/indicator-engine

# Default config (readable by all)
COPY --chmod=644 indicator-engine/config.json.example /etc/indicator-engine/config.json

# User is set at runtime via docker-compose (user: "${UID}:${GID}")
ENTRYPOINT ["indicator-engine"]
CMD ["--config", "/etc/indicator-engine/config.json", "--mode=both"]
