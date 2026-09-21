#!/usr/bin/env bash
# Прогнати весь ланцюг міграцій на одноразовому Postgres у Docker.
#
# Навіщо: міграції неможливо перевірити на SQLite (тести піднімають схему через
# create_all і міграції взагалі не виконують), а ганяти їх на dev/прод-базі, щоб
# «просто подивитись», не можна. Цей скрипт піднімає порожній контейнер на
# нестандартному порту, проганяє `flask db upgrade` з нуля, перевіряє аудит
# переліків і прибирає за собою.
#
#   ./scripts/verify_migrations.sh
#
# Вихід 0 — ланцюг застосувався. Ненульовий — міграція впала, дивись вивід.
set -euo pipefail

CONTAINER=crm_migration_check
PORT=55433
DB_USER=kvitkova_user
DB_PASS=kvitkova_password
DB_NAME=kvitkova_crm
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:${PORT}/${DB_NAME}"
export FLASK_APP=run.py

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "▶ Піднімаю одноразовий Postgres (порт ${PORT})…"
cleanup
docker run -d --name "$CONTAINER" \
  -e POSTGRES_USER="$DB_USER" \
  -e POSTGRES_PASSWORD="$DB_PASS" \
  -e POSTGRES_DB="$DB_NAME" \
  -p "${PORT}:5432" postgres:15 >/dev/null

for _ in $(seq 1 60); do
  docker exec "$CONTAINER" pg_isready -U "$DB_USER" >/dev/null 2>&1 && break
  sleep 1
done

echo "▶ flask db upgrade (весь ланцюг із нуля)…"
flask db upgrade

echo "▶ Поточний head:"
flask db current

echo "▶ flask audit-enum-values (на порожній базі — димовий тест самої команди)…"
flask audit-enum-values

echo "✅ Ланцюг міграцій застосувався без помилок."
echo "   Увага: це порожня база. Міграція з унікальностями"
echo "   (add_referential_integrity) може впасти на реальних даних —"
echo "   її треба окремо прогнати на копії прод-дампу."
