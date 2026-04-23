# =============================================================================
# Stage 1 — builder
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Stage 2 — runtime
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY worker.py .

# Non-root user — same reasoning as the API Dockerfile.
RUN useradd --system --uid 1001 --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# The worker has no HTTP server, so we can't probe a URL.
# Instead we write a sentinel file at startup and check it exists.
# The worker.py writes /tmp/worker_healthy on first successful Redis
# connection (see worker.py). This proves the process is alive AND
# connected to Redis — not just that the PID exists.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD test -f /tmp/worker_healthy

# Exec form so SIGTERM goes directly to the Python process (PID 1),
# triggering the graceful shutdown handler we added in FIX-06.
CMD ["python", "worker.py"]
