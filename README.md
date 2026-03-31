# CRM Квіткова Повня

> CRM-система для управління квітковим бізнесом: клієнти, підписки,
> замовлення, доставки, кур'єри та оптимізація маршрутів.

---

## Features

- Управління замовленнями та підписками (разові, Weekly / Bi-weekly / Monthly)
- CRM клієнтів з балансом і знижками
- Доставки та кур'єри
- Генерація та оптимізація маршрутів
- Звіти та транзакції
- Імпорт даних з CSV
- Telegram бот для кур'єрів
- Рольова система (admin / manager / florist)
- Подарункові сертифікати
- Транзакції

---

## Tech Stack

- **Backend:** Python 3.12, Flask, SQLAlchemy, Alembic
- **Database:** PostgreSQL 15
- **Frontend:** Jinja2, Bootstrap 5, Tailwind CSS v3
- **Bot:** python-telegram-bot 20.7
- **Deploy:** Docker Compose

---

## Quick Start

```bash
git clone <repo-url>
cd crmKvitkovaPovnya
cp env.example .env
docker compose up -d
docker compose exec web python scripts/seed_settings.py
docker compose exec web flask ensure-admin
```

---

## Roles

| Role    | Access         |
|---------|----------------|
| admin   | full access    |
| manager | business logic |
| florist | /florist only  |

---

## ENV

```env
POSTGRES_PASSWORD=your_password
SECRET_KEY=your_secret_key
TELEGRAM_BOT_TOKEN=...
DEPOT_ADDRESS=Київ, вул. Прикладна 1
ROUTE_OPTIMIZER_URL=http://...
```

---

## Docker

```bash
docker compose up -d
docker compose logs -f web
docker compose restart web
docker compose build web && docker compose up -d
```

---

## DB Migrations

```bash
docker compose exec web flask db upgrade
docker compose exec web flask db history
docker compose exec web flask db current
```

---

## Users

```bash
# Admin (з env змінних ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD)
docker compose exec web flask ensure-admin

# Florist (інтерактивно)
docker compose exec web flask create-florist
```

---

## Tests

```bash
pytest tests/unit/ -v          # всі юніт тести
pytest tests/unit/ --tb=short  # з коротким трейсом
```

Чек-лист тестів: [`tests/CHECKLIST.md`](tests/CHECKLIST.md)

---

## Backup

### Створити бекап

```bash
# Через скрипт (зберігається в ./backups/, створює директорію автоматично)
python3 scripts/database_backup.py create

# Або напряму через pg_dump
# Прапор --clean --if-exists додає DROP перед CREATE — це дозволяє відновлювати на існуючу БД
mkdir -p backups && docker compose exec -T postgres pg_dump --clean --if-exists -U kvitkova_user kvitkova_crm > backups/backup_$(date +%Y%m%d_%H%M%S).sql
```

### Список наявних бекапів

```bash
python3 scripts/database_backup.py list
```

### Відновити з бекапу

> **Важливо:** бекап має бути створений командами вище (з `--clean --if-exists`).
> Якщо бекап старий (без `--clean`), спочатку скинь схему вручну (крок нижче).

```bash
# Через скрипт
python3 scripts/database_backup.py restore backups/kvitkova_crm_backup_YYYYMMDD_HHMMSS.sql

# Або напряму через psql
docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm < backups/kvitkova_crm_backup_YYYYMMDD_HHMMSS.sql
```

**Якщо бекап без `--clean` (старий формат) — отримаєш помилки "already exists". Спочатку очисти схему:**

```bash
# Очистити всі таблиці (дані видаляться!)
docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Потім відновити
docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm < backups/kvitkova_crm_backup_YYYYMMDD_HHMMSS.sql

# Після відновлення повторно застосувати міграції (на випадок якщо бекап старіший за поточну схему)
docker compose exec web flask db upgrade
```

### Повністю видалити БД та почати з нуля

```bash
# 1. Зупинити всі контейнери
docker compose down

# 2. Видалити volume з даними PostgreSQL
docker volume rm crmkvitkovapovnya_postgres_data

# 3. Запустити заново — БД створиться автоматично і міграції застосуються
docker compose up -d

# 4. Наповнити початковими налаштуваннями (міста, розміри, типи доставки)
docker compose exec web python scripts/seed_settings.py

# 5. Створити адміна (з env змінних ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD)
docker compose exec web flask ensure-admin
```

> Щоб дізнатись точну назву volume: `docker volume ls | grep postgres`

---

## Import

- `/import/kvitkovapovnya`

---

## Architecture

```
app/
├── blueprints/   # Route handlers (orders, clients, couriers, florist…)
├── models/       # SQLAlchemy models
├── services/     # Business logic
├── templates/    # Jinja2 templates
└── static/       # CSS (Tailwind) + JS
```

---

## Docs

| Файл | Зміст |
|------|-------|
| [`docs/BUSINESS_LOGIC.md`](docs/BUSINESS_LOGIC.md) | Бізнес-правила, флоу, endpoint map |
| [`docs/BUGS_AND_MISSING_FEATURES.md`](docs/BUGS_AND_MISSING_FEATURES.md) | Відомі баги, missing features, підозрілі місця |
| [`docs/PERFORMANCE_PLAN.md`](docs/PERFORMANCE_PLAN.md) | Пріоритети оптимізації |
| [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md) | Чек-лист для нових фіч, правила міграцій |
| [`CLAUDE.md`](CLAUDE.md) | Інструкції для AI-асистента (стек, команди, патерни) |

---

## Author

Vladyslav Bilobrov
