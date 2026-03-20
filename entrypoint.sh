#!/bin/sh

set -e

# Database config (with defaults)
# PG_HOST="${DB_HOST:-postgres_db}"
PG_HOST="${DB_HOST:-db}"
# PG_PORT="${DB_PORT:-5432}"
PG_PORT=5432
PG_USER="${DB_USER}"
PG_DB="${DB_NAME}"

echo "[entrypoint] Starting container initialization..."

echo "[entrypoint] Checking database availability at ${PG_HOST}:${PG_PORT}..."

# Wait until PostgreSQL is ready
while ! pg_isready -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; do
  echo "[entrypoint] Database is not ready yet..."
  sleep 2
done

echo "[entrypoint] Database connection established"

# Apply migrations
echo "[entrypoint] Applying migrations..."
alembic upgrade head
echo "[entrypoint] Migrations successfully applied"

echo "[entrypoint] Launching application: gunicorn src.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT}"
exec gunicorn src.main:app \
     --workers 1 \
     --worker-class uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:${PORT}