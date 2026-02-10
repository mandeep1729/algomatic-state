# Multi-stage build for indicator-engine

# ---- Build Stage ----
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libpq-dev \
    libhiredis-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Build TA-Lib from source (v0.4.0)
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz \
    && tar xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr/local \
    && make -j$(nproc) \
    && make install \
    && cd / && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

WORKDIR /build

# Copy source
COPY CMakeLists.txt .
COPY src/ src/
COPY tests/ tests/

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
    libpq5 \
    libhiredis0.14 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib shared library
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
RUN ldconfig

# Copy the binary
COPY --from=builder /build/build/indicator-engine /usr/local/bin/indicator-engine

# Default config
COPY config.json.example /etc/indicator-engine/config.json

ENTRYPOINT ["indicator-engine"]
CMD ["--config", "/etc/indicator-engine/config.json", "--mode=both"]
