FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git

WORKDIR /app

# Copy go.mod/sum first for better layer caching.
COPY data-service/go.mod data-service/go.sum ./data-service/
COPY proto/gen/go/ ./proto/gen/go/

WORKDIR /app/data-service
RUN go mod download

# Copy source and build.
COPY data-service/ .
RUN CGO_ENABLED=0 GOOS=linux go build -o /data-service ./cmd/data-service

# Install grpc_health_probe for container health checks.
RUN GOBIN=/usr/local/bin go install github.com/grpc-ecosystem/grpc-health-probe@latest

# --- Runtime ---
FROM alpine:3.20

RUN apk add --no-cache ca-certificates

COPY --from=builder /data-service /usr/local/bin/data-service
COPY --from=builder /usr/local/bin/grpc_health_probe /usr/local/bin/grpc_health_probe

EXPOSE 50051

ENTRYPOINT ["data-service"]
