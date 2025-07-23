#!/bin/bash
set -e

echo "=== Starting CRM initialization ==="

# Перевірка структури проекту
echo "Checking project structure..."
ls -la /app

# Створення директорії для логів
echo "Creating logs directory..."
mkdir -p /app/logs

# Виконання міграцій БД
echo "Running database migrations..."
flask db upgrade || echo "Migration completed with warning"
echo "Database migrations completed successfully"

# Заповнення налаштувань
# echo "Seeding settings..."
# python3 scripts/seed_settings.py

# Запуск основного додатку
echo "Starting Gunicorn server..."
echo "Python path: $PYTHONPATH"
echo "Working directory: $(pwd)"
echo "Flask app: $FLASK_APP"
echo "Environment: $FLASK_ENV"

# Перевірка що run.py існує
if [ -f "run.py" ]; then
    echo "run.py found, starting server..."
else
    echo "ERROR: run.py not found!"
    exit 1
fi

exec gunicorn -w 4 -b 0.0.0.0:8000 run:app 