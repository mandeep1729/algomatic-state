# Stage 1: build TA-Lib C library
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ make wget ca-certificates libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr/local \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Stage 2: runtime
FROM python:3.12-slim

# Copy TA-Lib shared libraries and headers from builder
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
COPY --from=builder /usr/local/include/ta-lib /usr/local/include/ta-lib
RUN ldconfig

# Create non-root user for security
RUN groupadd --gid 1000 trader && \
    useradd --uid 1000 --gid trader --shell /bin/bash --create-home trader

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=trader:trader . .

# Create logs directory with correct ownership
RUN mkdir -p /app/logs && chown trader:trader /app/logs

# Switch to non-root user
USER trader

CMD ["python", "-m", "src.agent.main"]
