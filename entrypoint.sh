#!/bin/sh
set -e

echo "Running database migrations..."
flask db upgrade

echo "Creating admin user if not exists..."
flask ensure-admin

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 140 run:app
