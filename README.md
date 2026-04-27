# HNG Stage 2 — Job Processing System

A containerised multi-service job processing application consisting of a Node.js frontend, a Python/FastAPI backend, a Python worker, and a Redis queue — all wired together with Docker Compose and shipped via a full CI/CD pipeline on GitHub Actions.

---

## Architecture

```
Browser
   │
   ▼
┌─────────────┐        ┌─────────────┐
│  Frontend   │──────▶ │     API     │
│  (Node.js)  │        │  (FastAPI)  │
│  port 3000  │        │  port 8000  │
└─────────────┘        └──────┬──────┘
                              │  lpush / hset
                              ▼
                       ┌─────────────┐
                       │    Redis    │
                       │  (internal) │
                       └──────┬──────┘
                              │  brpop
                              ▼
                       ┌─────────────┐
                       │   Worker    │
                       │  (Python)   │
                       └─────────────┘
```

- **Frontend** — Express server that accepts job submissions and polls job status
- **API** — FastAPI service that creates jobs in Redis and serves status updates
- **Worker** — Python process that dequeues jobs, processes them, and updates their status
- **Redis** — Shared message queue and job state store (internal only, not exposed to host)

All services communicate over a named internal Docker network (`app-net`). Only the frontend is exposed to the host on port 3000.

---

## Prerequisites

Make sure the following are installed on your machine before proceeding.

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Git | 2.35+ | `git --version` |
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.20+ (bundled with Docker Desktop) | `docker compose version` |

Docker Desktop on Windows or Mac includes Docker Compose v2 out of the box. On Linux, install the `docker-compose-plugin` package.

---

## Quick Start (fresh machine)

### 1. Clone the repository

```bash
git clone https://github.com/kachi-cmd/hng14-stage2-devops-k.git
cd hng14-stage2-devops-k
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

The default values in `.env.example` work out of the box for local development. Open `.env` if you want to change the frontend port or resource limits — otherwise leave it as-is.

### 3. Bring the stack up

```bash
docker compose up --build -d --wait
```

What this does:
- `--build` builds all three images from source before starting
- `-d` runs containers in the background (detached mode)
- `--wait` holds the command until every service has passed its healthcheck — so when the command returns, the stack is fully ready

This takes approximately **60–90 seconds** on first run while images are built and dependencies are installed. Subsequent runs are faster due to Docker layer caching.

### 4. Verify the stack is healthy

```bash
docker compose ps
```

Expected output — all four services should show `healthy`:

```
NAME                             SERVICE    STATUS              PORTS
hng14-stage2-devops-k-redis-1    redis      running (healthy)   6379/tcp
hng14-stage2-devops-k-api-1      api        running (healthy)   8000/tcp
hng14-stage2-devops-k-worker-1   worker     running (healthy)
hng14-stage2-devops-k-frontend-1 frontend   running (healthy)   0.0.0.0:3000->3000/tcp
```

Note that Redis and the API have no host port mapping except the frontend on `3000`. This is intentional — internal services are not accessible from outside the Docker network.

---

## Using the Application

### Via the browser

Open [http://localhost:3000](http://localhost:3000) in your browser. You will see the Job Processor Dashboard. Click **Submit New Job** to create a job and watch it move from `queued` to `completed` in real time.

### Via the command line

**Submit a job:**
```bash
curl -X POST http://localhost:3000/submit
```

Response:
```json
{"job_id": "a3f7c821-1234-4abc-9def-000000000001"}
```

**Check job status:**
```bash
curl http://localhost:3000/status/<job_id>
```

Response (immediately after submit):
```json
{"job_id": "a3f7c821-1234-4abc-9def-000000000001", "status": "queued"}
```

Response (after ~2 seconds, once the worker processes it):
```json
{"job_id": "a3f7c821-1234-4abc-9def-000000000001", "status": "completed"}
```

**One-liner — submit and poll automatically:**
```bash
JOB_ID=$(curl -s -X POST http://localhost:3000/submit | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo "Submitted: $JOB_ID"
sleep 3
curl -s http://localhost:3000/status/$JOB_ID
```

---

## Stopping the Stack

```bash
# Stop and remove containers (preserves built images)
docker compose down

# Stop, remove containers AND delete volumes
docker compose down -v

# Stop without removing containers (can be restarted with docker compose start)
docker compose stop
```

---

## Rebuilding After Code Changes

If you change any source file and want to rebuild:

```bash
docker compose up --build -d --wait
```

Docker will only rebuild the images whose source files changed — unchanged services reuse their cached layers.

---

## Environment Variables Reference

All variables are defined in `.env.example`. Copy to `.env` and adjust as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `production` | Application environment |
| `IMAGE_TAG` | `latest` | Docker image tag (set to git SHA in CI) |
| `FRONTEND_PORT` | `3000` | Host port the frontend is exposed on |
| `REDIS_CPU_LIMIT` | `0.25` | CPU limit for the Redis container |
| `REDIS_MEMORY_LIMIT` | `128M` | Memory limit for the Redis container |
| `API_CPU_LIMIT` | `0.5` | CPU limit for the API container |
| `API_MEMORY_LIMIT` | `256M` | Memory limit for the API container |
| `WORKER_CPU_LIMIT` | `0.5` | CPU limit for the worker container |
| `WORKER_MEMORY_LIMIT` | `256M` | Memory limit for the worker container |
| `FRONTEND_CPU_LIMIT` | `0.25` | CPU limit for the frontend container |
| `FRONTEND_MEMORY_LIMIT` | `128M` | Memory limit for the frontend container |

---

## CI/CD Pipeline

The pipeline runs automatically on every push via GitHub Actions. It has six strictly ordered stages — a failure in any stage prevents all subsequent stages from running.

```
lint → test → build → security scan → integration test → deploy
```

| Stage | What it does |
|-------|-------------|
| **Lint** | flake8 (Python), eslint (JavaScript), hadolint (Dockerfiles) |
| **Test** | 6 pytest unit tests for the API with Redis mocked via fakeredis. Coverage report uploaded as artifact |
| **Build** | Builds all 3 images, tags with git SHA and `latest`, pushes to a local registry service container |
| **Security scan** | Trivy scans all 3 images — pipeline fails on any CRITICAL CVE. SARIF results uploaded as artifact |
| **Integration test** | Full stack brought up inside the runner, a real job is submitted and polled until `completed`, stack torn down cleanly regardless of outcome |
| **Deploy** | Runs on pushes to `main` only. Performs a rolling update — new container must pass its healthcheck within 60 seconds before the old one is stopped. Aborts safely if health check does not pass |

---

## Project Structure

```
.
├── api/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── main.py
│   └── requirements.txt
├── worker/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── worker.py
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── app.js
│   ├── package.json
│   ├── package-lock.json
│   └── views/
│       └── index.html
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── .env.example
├── .gitignore
├── FIXES.md
└── README.md
```

---

## Bugs Fixed

All bugs found in the starter repository are documented in detail in [FIXES.md](./FIXES.md), including the file, line number, nature of the problem, and the exact fix applied. A total of 10 bugs were identified and resolved.

---

## Security Notes

- `.env` is listed in `.gitignore` and is never committed to the repository
- Redis is not exposed on the host machine — it is only accessible within the internal Docker network
- All containers run as a non-root user (`appuser`, UID 1001)
- All images are built using multi-stage builds — no build tools or dev dependencies in the final images
- The pipeline fails on any CRITICAL severity CVE finding in any image
