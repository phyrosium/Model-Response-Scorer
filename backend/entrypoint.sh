#!/bin/sh
# Runs once per container start, before the app. Compose already waits on the
# db healthcheck, so Postgres is reachable by the time this runs.
set -e

echo "entrypoint: applying migrations"
alembic upgrade head

echo "entrypoint: seeding starter data"
python seed.py

exec "$@"
