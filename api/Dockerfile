# =============================================================================
# Stage 1 — builder
# Install dependencies in an isolated stage so pip and build tools never
# make it into the final image. The --prefix flag installs everything into
# /install, which we copy wholesale into the runtime stage.
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Stage 2 — runtime
# Start from the same slim base. Copy only the installed packages from the
# builder and the application source. No pip, no build tools, no cache.
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source — explicitly named so nothing unexpected is included.
# .dockerignore should also exclude .env, __pycache__, *.pyc, .git etc.
COPY main.py .

# Create a dedicated non-root user and group, then transfer ownership.
# Running as root inside a container means a container escape gives the
# attacker root on the host. A non-root user limits that blast radius.
RUN useradd --system --uid 1001 --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# Document the port the application listens on. This is metadata only —
# it does not publish the port. docker-compose handles actual port binding.
EXPOSE 8000

# Docker checks this command on the interval defined in docker-compose.
# We use python's built-in urllib so we don't need curl installed in the image.
# --retries, --interval, --timeout are all set in docker-compose, not here,
# so this instruction just defines the probe command itself.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run uvicorn directly (not via shell) so it receives signals like SIGTERM
# properly. Shell form (CMD "uvicorn ...") means PID 1 is /bin/sh which
# swallows signals and your container takes 10s to stop every time.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
