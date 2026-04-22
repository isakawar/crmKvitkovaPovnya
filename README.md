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
- AI Асистент (чат для менеджерів і адмінів, вмикається/вимикається в налаштуваннях)

---

## Tech Stack

- **Backend:** Python 3.12, Flask, SQLAlchemy, Alembic
- **Database:** PostgreSQL 15
- **Cache:** Redis 7
- **Frontend:** Jinja2, Bootstrap 5, Tailwind CSS v3
- **Bot:** python-telegram-bot 20.7
- **AI:** OpenAI-compatible API (Gemini, OpenRouter, etc.)
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

Скопіюй `env.example` в `.env` і заповни значення:

```env
# Database
POSTGRES_PASSWORD=your_password
SECRET_KEY=your_secret_key

# Admin
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your_password

# Telegram bot
TELEGRAM_BOT_TOKEN=...

# Route optimizer
DEPOT_ADDRESS=Київ, вул. Прикладна 1
ROUTE_OPTIMIZER_URL=http://...
OPTIMIZER_API_KEY=

# AI Agent (OpenAI-compatible)
AI_API_KEY=your_key
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_MODEL=gemini-2.5-flash

# Redis
REDIS_URL=redis://redis:6379/0
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

## CI / Releases

При merge PR в `main` автоматично:
1. Запускаються юніт тести
2. Якщо тести пройшли — створюється новий semver тег і GitHub Release з changelog

Версія визначається по [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix в commit | Bump |
|-----------------|------|
| `BREAKING CHANGE` | major |
| `feat:` | minor |
| `fix:`, решта | patch |

### Деплой на сервер (ручний)

```bash
git fetch --tags
git checkout v0.4.0           # переключитись на потрібну версію
docker compose up -d --build  # перезапустити
```

Rollback:
```bash
git checkout v0.3.0
docker compose up -d --build
```

---

## Backup

> Всі команди виконуються на хості (не через `docker compose exec web`).
> Shell-редиректи `>` і `<` працюють з файлами на хості.

### Створити бекап

```bash
mkdir -p backups && docker compose exec -T postgres pg_dump --clean --if-exists -U kvitkova_user kvitkova_crm > backups/backup_$(date +%Y%m%d_%H%M%S).sql
```

Файл збережеться в `./backups/` на хості.

### Відновити з бекапу

```bash
docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm < backups/backup_YYYYMMDD_HHMMSS.sql
```

**Якщо отримуєш помилки `already exists`** (бекап створений без `--clean`):

```bash
# 1. Очистити схему
docker compose exec postgres psql -U kvitkova_user -d kvitkova_crm \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 2. Відновити
docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm \
  < backups/backup_YYYYMMDD_HHMMSS.sql

# 3. Застосувати міграції
docker compose exec web flask db upgrade
```

### Повністю видалити БД та почати з нуля

Дані PostgreSQL зберігаються фізично у папці `./data/postgres/` всередині проекту (не в Docker volume).

```bash
# 1. Зупинити контейнери
docker compose down

# 2. Видалити папку з даними БД
rm -rf ./data/postgres

# 3. Запустити — postgres стартує з чистою БД
docker compose up -d

# 4. Застосувати міграції
docker compose exec web flask db upgrade

# 5. Наповнити початковими налаштуваннями
docker compose exec web python scripts/seed_settings.py

# 6. Створити адміна
docker compose exec web flask ensure-admin
```

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
