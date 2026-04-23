import redis
import time
import os
import signal

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379))
)

running = True


def handle_sigterm(signum, frame):
    global running
    running = False


signal.signal(signal.SIGTERM, handle_sigterm)


def process_job(job_id):
    print(f"Processing job {job_id}")
    time.sleep(2)
    r.hset(f"job:{job_id}", "status", "completed")
    print(f"Done: {job_id}")


# Write sentinel file once Redis connection is confirmed healthy.
# The Dockerfile HEALTHCHECK probes this file so Docker knows the
# worker is alive and connected — not just that the process started.
r.ping()
open("/tmp/worker_healthy", "w").close()
print("Worker connected to Redis, ready to process jobs")

while running:
    job = r.brpop("jobs", timeout=5)
    if job:
        _, job_id = job
        process_job(job_id.decode())

print("Worker shutting down cleanly")
