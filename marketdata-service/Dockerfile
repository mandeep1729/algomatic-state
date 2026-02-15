# Build stage
FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o marketdata-service ./cmd/marketdata-service

# Runtime stage
FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /build/marketdata-service /usr/local/bin/marketdata-service
COPY config.json.example /etc/marketdata-service/config.json
RUN mkdir -p /var/log/marketdata-service
ENTRYPOINT ["marketdata-service"]
CMD ["--config", "/etc/marketdata-service/config.json", "--mode=both"]
