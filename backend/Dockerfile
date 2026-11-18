# ==============================================================================
# Multi-Stage Dockerfile for LoanTrack Backend API
# Base: python:3.12-slim (Strictly pinned, never latest)
# Security: Non-root user execution
# Size target: < 300 MB
# ==============================================================================

# Stage 1: Build & dependency resolution
FROM python:3.12-slim AS builder

WORKDIR /build

# Install compilation tools only in builder stage
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Cache optimization: Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install packages into a separate user prefix
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Minimal runtime image
FROM python:3.12-slim AS runtime

# Install only curl for container HEALTHCHECK
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Explicit non-root user and group creation
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false -m appuser

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Environment configuration
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Layer caching: Application source code copied after dependencies
COPY --chown=appuser:appgroup main.py .

# Switch to explicit non-root user
USER appuser

EXPOSE 8000

# Container HEALTHCHECK targeting process liveness
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
