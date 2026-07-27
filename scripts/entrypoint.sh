#!/usr/bin/env sh
set -e

echo "Ensuring the database exists..."
python -c "from app.config import get_settings; from app.db.bootstrap import ensure_database_exists; ensure_database_exists(get_settings().database_url)"

echo "Applying database migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "Seeding example proposals..."
  python -m scripts.seed
fi

echo "Starting application on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
