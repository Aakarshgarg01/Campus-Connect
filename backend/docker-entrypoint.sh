#!/bin/sh
# Apply database migrations, then start the API.
# --proxy-headers: behind the host's load balancer, use the real client IP (needed for the
# per-IP login rate limit) and scheme. FORWARDED_ALLOW_IPS defaults to "*" because managed
# hosts (Render, Railway, Fly) only expose the container through their own proxy.
set -e

alembic upgrade head

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
