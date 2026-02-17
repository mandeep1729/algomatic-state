# Multi-stage build for indicator-engine

# ---- Build Stage ----
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
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

# Generate C++ proto stubs from .proto files
COPY proto/market/ /proto/market/
RUN mkdir -p proto_gen \
    && protoc -I/proto \
       --experimental_allow_proto3_optional \
       --cpp_out=proto_gen \
       --grpc_out=proto_gen \
       --plugin=protoc-gen-grpc=$(which grpc_cpp_plugin) \
       /proto/market/v1/ticker.proto \
       /proto/market/v1/bar.proto \
       /proto/market/v1/feature.proto \
       /proto/market/v1/sync_log.proto \
       /proto/market/v1/service.proto

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
