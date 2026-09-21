#!/bin/sh
set -e

echo "Running database migrations..."
flask db upgrade

echo "Creating admin user if not exists..."
flask ensure-admin

echo "Starting application..."
# gevent workers so /inbox/stream (SSE) can hold a connection open per
# manager tab without blocking the other 3 workers' worth of requests —
# a sync worker would be pinned to that one connection for its whole life.
exec gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class gevent --worker-connections 250 --timeout 140 \
  --access-logfile - \
  --access-logformat '%(h)s "%(r)s" %(s)s %(b)s "%(a)s"' \
  run:app
