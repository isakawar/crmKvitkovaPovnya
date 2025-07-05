#!/bin/bash
set -e

echo "=== Starting CRM initialization ==="

# Перевірка структури проекту
echo "Checking project structure..."
ls -la /app

# Виконання міграцій БД
echo "Running database migrations..."
flask db upgrade

# Заповнення налаштувань
echo "Seeding settings..."
python3 app/scripts/seed_settings.py

# Запуск основного додатку
echo "Starting Gunicorn server..."
exec gunicorn -w 4 -b 0.0.0.0:8000 run:app 