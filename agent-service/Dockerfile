# Multi-stage build for agent-service
# Build context must be the project root (agents/) to access go-strats/ for replace directive

# --- Build stage ---
FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git

WORKDIR /build

# Copy go-strats dependency first (for caching)
COPY go-strats/go.mod go-strats/go.sum ./go-strats/
COPY go-strats/pkg/ ./go-strats/pkg/

# Copy data-service dependency (needed by go-strats)
COPY data-service/go.mod data-service/go.sum ./data-service/
COPY data-service/internal/ ./data-service/internal/

# Copy agent-service
COPY agent-service/go.mod agent-service/go.sum* ./agent-service/

WORKDIR /build/agent-service
RUN go mod download

COPY agent-service/ ./

RUN CGO_ENABLED=0 GOOS=linux go build -o /agent-service ./cmd/agent-service

# --- Runtime stage ---
FROM alpine:3.20

RUN apk add --no-cache ca-certificates procps

COPY --from=builder /agent-service /usr/local/bin/agent-service

ENTRYPOINT ["agent-service"]
