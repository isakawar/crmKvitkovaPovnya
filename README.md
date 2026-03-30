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

```bash
docker compose exec web python scripts/database_backup.py create
```

---

## Import

- `/import`
- `/import/operational`
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
