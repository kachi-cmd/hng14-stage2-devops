# FIXES.md

This document records every bug found in the starter repository, including the file, line number, nature of the problem, and the exact fix applied. Bugs are grouped by service.

---

## API Service (`api/`)

### FIX-01
- **File:** `api/main.py`
- **Line:** 8
- **Problem:** Redis client was hardcoded to connect to `host="localhost"`. Inside Docker, each container has its own network namespace and `localhost` resolves to the container itself — not the Redis service. This causes an immediate connection failure at runtime; the API cannot reach Redis at all.
- **Fix:** Replaced hardcoded `"localhost"` with `os.getenv("REDIS_HOST", "redis")` so the host is read from the environment variable `REDIS_HOST`, falling back to `"redis"` which is the Docker Compose service name. Port is similarly read from `os.getenv("REDIS_PORT", 6379)`.
- **Before:**
  ```python
  r = redis.Redis(host="localhost", port=6379)
  ```
- **After:**
  ```python
  r = redis.Redis(
      host=os.getenv("REDIS_HOST", "redis"),
      port=int(os.getenv("REDIS_PORT", 6379))
  )
  ```

---

### FIX-02
- **File:** `api/main.py`
- **Line:** 13
- **Problem:** The API pushed job IDs onto a Redis list named `"job"` (singular). The worker consumed from a list named `"jobs"` (plural). These are two different keys in Redis — jobs submitted by the API were never seen by the worker. The system appeared to function (no crash, no error returned) but jobs would remain in `"queued"` status forever, silently accumulating in the wrong queue.
- **Fix:** Changed the queue key in the API from `"job"` to `"jobs"` to match the key the worker reads from.
- **Before:**
  ```python
  r.lpush("job", job_id)
  ```
- **After:**
  ```python
  r.lpush("jobs", job_id)
  ```

---

### FIX-03
- **File:** `api/main.py`
- **Line:** (missing — no `/health` route existed in the file)
- **Problem:** No `/health` endpoint was defined. Docker Compose `healthcheck` directives, the `depends_on: condition: service_healthy` configuration, and the CI/CD deploy stage all rely on this endpoint to determine whether the API is ready to serve traffic. Without it, every health check times out, dependent services never start, and the rolling deploy logic cannot verify the new container is healthy before cutting over.
- **Fix:** Added a `/health` GET endpoint that returns HTTP 200 with `{"status": "ok"}`.
- **After:**
  ```python
  @app.get("/health")
  def health():
      return {"status": "ok"}
  ```

---

### FIX-04
- **File:** `api/.env`
- **Line:** 1–2 (entire file)
- **Problem:** A `.env` file containing a real credential (`REDIS_PASSWORD=supersecretpassword123`) was committed directly into the repository. Committing secrets to version control is a critical security violation — once pushed, the secret is permanently in git history even if the file is later deleted. Additionally, the password defined in this file was never actually read or used anywhere in the application code, meaning Redis auth was silently non-functional.
- **Fix:** Added `.env` to `.gitignore` at the repo root. Removed `api/.env` from git tracking using `git rm --cached api/.env`. Created `api/.env.example` with placeholder values to document required variables without exposing secrets.
- **`.env.example`:**
  ```dotenv
  REDIS_HOST=redis
  REDIS_PORT=6379
  REDIS_PASSWORD=your_redis_password_here
  APP_ENV=production
  API_URL=http://api:8000
  FRONTEND_PORT=3000
  ```

---

## Worker Service (`worker/`)

### FIX-05
- **File:** `worker/worker.py`
- **Line:** 3
- **Problem:** Same fatal networking bug as FIX-01. The worker's Redis client was hardcoded to `host="localhost"`. Inside Docker, this resolves to the worker container itself, not the Redis service. The worker cannot connect to Redis and cannot dequeue or process any jobs.
- **Fix:** Replaced hardcoded `"localhost"` with `os.getenv("REDIS_HOST", "redis")`, matching the same pattern applied to the API.
- **Before:**
  ```python
  r = redis.Redis(host="localhost", port=6379)
  ```
- **After:**
  ```python
  r = redis.Redis(
      host=os.getenv("REDIS_HOST", "redis"),
      port=int(os.getenv("REDIS_PORT", 6379))
  )
  ```

---

### FIX-06
- **File:** `worker/worker.py`
- **Line:** 11 (`while True:` loop)
- **Problem:** The worker ran as a bare `while True` loop with no signal handling. When Docker stops a container it sends `SIGTERM` first, then forcibly kills the process after 10 seconds if it has not exited. With no `SIGTERM` handler, the worker is killed mid-job with no opportunity to finish processing or update the job status in Redis. Any job being processed at shutdown time is permanently lost, left stuck in `"queued"` status with no record of what happened.
- **Fix:** Registered a `SIGTERM` signal handler that sets a `running` flag to `False`. The main loop checks this flag on each iteration, allowing the current job to complete cleanly before the process exits.
- **Before:**
  ```python
  while True:
      job = r.brpop("job", timeout=5)
      if job:
          _, job_id = job
          process_job(job_id.decode())
  ```
- **After:**
  ```python
  running = True

  def handle_sigterm(signum, frame):
      global running
      running = False

  signal.signal(signal.SIGTERM, handle_sigterm)

  while running:
      job = r.brpop("jobs", timeout=5)
      if job:
          _, job_id = job
          process_job(job_id.decode())
  ```

---

## Frontend Service (`frontend/`)

### FIX-07
- **File:** `frontend/app.js`
- **Line:** 5
- **Problem:** The API base URL was hardcoded as `"http://localhost:8000"`. When the frontend runs inside a Docker container, `localhost` refers to the frontend container itself — not the API service. Every API call from the frontend fails with a connection refused error. This bug works locally (both processes on the same machine) but breaks unconditionally in any containerised environment.
- **Fix:** Replaced the hardcoded string with `process.env.API_URL || "http://api:8000"` so the URL is read from an environment variable injected at runtime, with the Docker Compose service name as the fallback.
- **Before:**
  ```javascript
  const API_URL = "http://localhost:8000";
  ```
- **After:**
  ```javascript
  const API_URL = process.env.API_URL || "http://api:8000";
  ```

---

### FIX-08
- **File:** `frontend/app.js`
- **Line:** (missing — no `/health` route existed in the file)
- **Problem:** No `/health` endpoint was defined on the Express server. Without it, the Docker `HEALTHCHECK` instruction in the Dockerfile has nothing to probe, causing the frontend container to remain in an `unhealthy` state indefinitely and blocking any services or pipeline steps that depend on it being healthy.
- **Fix:** Added a `/health` GET route that returns HTTP 200 with `{"status": "ok"}`.
- **After:**
  ```javascript
  app.get('/health', (req, res) => res.json({ status: 'ok' }));
  ```

---

### FIX-09
- **File:** `frontend/index.html`
- **Line:** `pollJob` function (approx. line 32–37)
- **Problem:** The polling function only terminated when job status was `"completed"`. If a job entered a `"failed"` state, or if the API returned an error response, the function continued polling indefinitely with no backoff and no exit condition. In a failure scenario this creates an unbounded loop of requests that never resolves.
- **Fix:** Added `"failed"` as a terminal status that also stops polling. Added a `maxRetries` counter (30 attempts × 2 second interval = 60 second timeout) to stop polling and surface an error if the job does not complete in time.
- **Before:**
  ```javascript
  if (data.status !== 'completed') {
      setTimeout(() => pollJob(id), 2000);
  }
  ```
- **After:**
  ```javascript
  if (data.status === 'completed' || data.status === 'failed') {
      return;
  }
  if (retries < 30) {
      setTimeout(() => pollJob(id, retries + 1), 2000);
  } else {
      renderJob(id, 'timed out');
  }
  ```

---

## Summary Table

| ID | File | Line | Category | Severity |
|----|------|------|----------|----------|
| FIX-01 | `api/main.py` | 8 | Docker networking — hardcoded localhost | Critical |
| FIX-02 | `api/main.py` | 13 | Queue key mismatch ("job" vs "jobs") | Critical |
| FIX-03 | `api/main.py` | — | Missing /health endpoint | High |
| FIX-04 | `api/.env` | 1–2 | Secret committed to repository | Critical |
| FIX-05 | `worker/worker.py` | 3 | Docker networking — hardcoded localhost | Critical |
| FIX-06 | `worker/worker.py` | 11 | No SIGTERM handler — jobs lost on shutdown | High |
| FIX-07 | `frontend/app.js` | 5 | Docker networking — hardcoded localhost | Critical |
| FIX-08 | `frontend/app.js` | — | Missing /health endpoint | High |
| FIX-09 | `frontend/index.html` | ~32 | Infinite polling loop on failure | Medium |
