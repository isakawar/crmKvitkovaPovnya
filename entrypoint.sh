#!/bin/sh
set -e

echo "Running database migrations..."
flask db upgrade

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 140 run:app
