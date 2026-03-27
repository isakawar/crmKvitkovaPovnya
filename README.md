# 🌸 CRM Квіткова Повня

> CRM-система для управління квітковим бізнесом: клієнти, підписки,
> замовлення, доставки, кур'єри та оптимізація маршрутів.

------------------------------------------------------------------------

## ✨ Features

-   📦 Управління замовленнями та підписками
-   👥 CRM клієнтів
-   🚚 Доставки та кур'єри
-   🧭 Генерація та оптимізація маршрутів
-   📊 Звіти та транзакції
-   📥 Імпорт даних з CSV (кастомні формати)
-   🤖 Telegram бот для кур'єрів
-   🧩 Рольова система (admin / manager / florist)

------------------------------------------------------------------------

## 🧱 Tech Stack

-   Backend: Python 3.12, Flask, SQLAlchemy, Alembic
-   Database: PostgreSQL 15
-   Frontend: Jinja2, Bootstrap 5, Tailwind CSS
-   Bot: python-telegram-bot
-   Deploy: Docker Compose

------------------------------------------------------------------------

## ⚡ Quick Start

``` bash
git clone <repo-url>
cd crmKvitkovaPovnya
cp env.example .env
docker compose up -d
docker compose exec web python scripts/seed_settings.py
docker compose exec web flask create-admin
```

------------------------------------------------------------------------

## 🔐 Roles

  Role      Access
  --------- ----------------
  admin     full access
  manager   business logic
  florist   /florist only

------------------------------------------------------------------------

## ⚙️ ENV

``` env
POSTGRES_PASSWORD=your_password
SECRET_KEY=your_secret_key
TELEGRAM_BOT_TOKEN=...
DEPOT_ADDRESS=Київ, вул. Прикладна 1
ROUTE_OPTIMIZER_URL=http://...
```

------------------------------------------------------------------------

## 🐳 Docker

``` bash
docker compose up -d
docker compose logs -f web
docker compose restart web
docker compose build web && docker compose up -d
```

------------------------------------------------------------------------

## 🧬 DB

``` bash
docker compose exec web flask db upgrade
docker compose exec web flask db history
docker compose exec web flask db current
```

------------------------------------------------------------------------

## 👤 Users

Команди запитують `username`, `email` та `password` інтерактивно.

``` bash
# Створити адміністратора
docker compose exec web flask create-admin

# Створити флориста
docker compose exec web flask create-florist
```

------------------------------------------------------------------------

## 💾 Backup

``` bash
docker compose exec web python scripts/database_backup.py create
```

------------------------------------------------------------------------

## 📥 Import

-   /import
-   /import/operational
-   /import/kvitkovapovnya

------------------------------------------------------------------------

## 🏗 Architecture

    app/
    ├── blueprints/
    ├── models/
    ├── services/
    ├── templates/
    └── static/

------------------------------------------------------------------------

## 👨‍💻 Author

Vladyslav Bilobrov
