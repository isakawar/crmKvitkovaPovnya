# CRM Kvіtkova Povnya

CRM-система для квіткового магазину. Управління замовленнями, доставками, кур'єрами та маршрутами.

Операційна документація по флоу (клієнт -> замовлення/підписка -> доставки -> маршрути):  
[`docs/PROJECT_FLOW.md`](docs/PROJECT_FLOW.md)

## Стек

- **Backend:** Python 3.12, Flask, SQLAlchemy, Alembic
- **Database:** PostgreSQL 15
- **Frontend:** Jinja2, Bootstrap 5, Leaflet.js
- **Telegram Bot:** python-telegram-bot
- **Route Optimizer:** зовнішній сервіс (REST API)
- **Deploy:** Docker Compose

---

## Структура проекту

```
app/
├── blueprints/
│   ├── auth/          # Авторизація
│   ├── clients/       # Клієнти
│   ├── couriers/      # Кур'єри
│   ├── deliveries/    # Доставки
│   ├── florist/       # Сторінка флориста (/florist)
│   ├── orders/        # Замовлення + оптимізатор маршрутів
│   ├── reports/       # Звіти
│   ├── routes/        # Збережені маршрути (/routes)
│   └── settings/      # Налаштування
├── models/            # SQLAlchemy моделі
├── services/          # Бізнес-логіка, route optimizer
├── telegram_bot/      # Telegram бот (handlers, keyboards, bot)
├── templates/         # Jinja2 шаблони
├── static/            # Статика
└── utils/             # Допоміжні утиліти

migrations/            # Alembic міграції
scripts/               # Утиліти для адміністрування
docs/                  # Документація
```

## Сторінки

| URL | Опис |
|-----|------|
| `/orders` | Список замовлень |
| `/deliveries` | Список доставок |
| `/clients` | Клієнти |
| `/couriers` | Кур'єри |
| `/route-generator` | Оптимізатор маршрутів |
| `/routes` | Збережені маршрути (призначення кур'єрів, відправка в Telegram) |
| `/reports` | Звіти |
| `/florist` | Сторінка флориста (тільки для user_type=florist) |
| `/settings` | Налаштування |

---

## Запуск (Docker)

```bash
# 1. Скопіюй env
cp env.example .env
# Заповни .env: TELEGRAM_BOT_TOKEN, POSTGRES_PASSWORD, ROUTE_OPTIMIZER_URL

# 2. Запуск
docker compose up -d

# 3. Створити адміна
docker compose exec web bash -c "cd /app && PYTHONPATH=/app python scripts/create_default_admin.py"
```

### Команди для розробки

```bash
# Застосувати зміни в коді (Python/HTML/CSS)
docker compose restart web

# Перебілдити (після змін у requirements.txt або Dockerfile)
docker compose build web && docker compose up -d

# Логи
docker compose logs -f web

# Міграція вручну
docker compose exec web flask db upgrade
```

---

## Повне скидання та ініціалізація БД

Якщо потрібно почати з чистої БД (наприклад, після додавання нових міграцій або при розгортанні на новому сервері):

### 1. Зупинити контейнери та видалити дані БД

```bash
docker compose down
rm -rf data/postgres
```

> Папка `data/postgres` — це volume PostgreSQL. Видалення очищає всі таблиці та дані.

### 2. Запустити контейнери (міграції застосуються автоматично)

```bash
docker compose up -d
```

Контейнер `web` при старті автоматично виконує `flask db upgrade` через `entrypoint.sh`.

### 3. Наповнити початковими даними

```bash
# Створити адміністратора (логін: admin, пароль: admin)
docker compose exec web bash -c "cd /app && PYTHONPATH=/app python scripts/create_default_admin.py"

# Заповнити довідники (міста, розміри, типи доставки, тощо)
docker compose exec web bash -c "cd /app && PYTHONPATH=/app python scripts/seed_settings.py"
```

### 4. Опційно: тестові дані

```bash
# Додати тестових клієнтів та доставки
docker compose exec web bash -c "cd /app && PYTHONPATH=/app python scripts/seed_test_data.py"
```

### Повна команда одним блоком

```bash
docker compose down && \
rm -rf data/postgres && \
docker compose up -d && \
sleep 10 && \
docker compose exec web bash -c "cd /app && PYTHONPATH=/app python scripts/create_default_admin.py" && \
docker compose exec web bash -c "cd /app && PYTHONPATH=/app python scripts/seed_settings.py"
```

---

## Основні таблиці БД

| Таблиця | Опис |
|---------|------|
| `user` | Користувачі (admin, manager, florist) |
| `client` | Клієнти (instagram, телефон) |
| `courier` | Кур'єри + telegram_chat_id |
| `order` | Замовлення (отримувач, адреса, розмір) |
| `delivery` | Доставки (дата, статус, кур'єр) |
| `delivery_routes` | Збережені маршрути |
| `route_deliveries` | Зупинки маршруту |

---

## Telegram бот

Кур'єр отримує пропозицію маршруту з кнопками **Прийняти / Відхилити**.
Після прийняття — отримує повний маршрут: адреси, отримувачі, телефони, час.

---

## Змінні середовища

```env
TELEGRAM_BOT_TOKEN=...
POSTGRES_PASSWORD=...
ROUTE_OPTIMIZER_URL=http://...
OPTIMIZER_API_KEY=
SECRET_KEY=...
```

Детально: [docs/ENV_SETUP.md](docs/ENV_SETUP.md)
