# ==============================================================================
# Multi-Stage Dockerfile for LoanTrack Frontend Tier
# Base: nginx:1.27.2-alpine (Strictly pinned, never latest)
# Security: Non-root user execution on unprivileged port 8080
# ==============================================================================

# Stage 1: Asset Preparation
FROM alpine:3.20 AS builder

WORKDIR /assets
COPY index.html .
COPY nginx.conf .

# Stage 2: Runtime Web Server
FROM nginx:1.27.2-alpine AS runtime

# Install curl for container health check
RUN apk add --no-cache curl

# Create explicit non-root user and group
RUN addgroup -g 10001 appgroup && \
    adduser -u 10001 -G appgroup -s /bin/sh -D appuser

# Configure directory permissions for non-root execution
RUN touch /var/run/nginx.pid && \
    chown -R appuser:appgroup /var/run/nginx.pid && \
    chown -R appuser:appgroup /var/cache/nginx && \
    chown -R appuser:appgroup /var/log/nginx && \
    chown -R appuser:appgroup /etc/nginx/conf.d

WORKDIR /usr/share/nginx/html

# Copy configuration and assets from builder
COPY --from=builder --chown=appuser:appgroup /assets/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=appuser:appgroup /assets/index.html /usr/share/nginx/html/index.html

# Switch to explicit non-root user
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
