# CRM Квіткова Повня

CRM-система для квіткового магазину. Управління клієнтами, замовленнями, підписками, доставками, кур'єрами та маршрутами.

---

## Стек

- **Backend:** Python 3.12, Flask, SQLAlchemy, Alembic
- **Database:** PostgreSQL 15
- **Frontend:** Jinja2, Bootstrap 5, Tailwind CSS v3
- **Telegram Bot:** python-telegram-bot 20.7
- **Deploy:** Docker Compose

---

## Змінні середовища

Скопіюй та заповни `.env`:

```bash
cp env.example .env
```

```env
POSTGRES_PASSWORD=your_password
SECRET_KEY=your_secret_key
TELEGRAM_BOT_TOKEN=...
DEPOT_ADDRESS=Київ, вул. Прикладна 1   # адреса депо для оптимізатора маршрутів
ROUTE_OPTIMIZER_URL=http://...          # зовнішній API оптимізації
```

---

## Розгортання (Docker)

### Перший запуск

```bash
# 1. Клонувати репо і перейти в папку
git clone <repo-url>
cd crmKvitkovaPovnya

# 2. Заповнити .env
cp env.example .env

# 3. Запустити контейнери
docker compose up -d

# Міграції застосовуються автоматично при старті через entrypoint.sh
# Зачекай 10-15 секунд поки БД та веб повністю піднімуться

# 4. Заповнити довідники (міста, розміри, типи доставки)
docker compose exec web python scripts/seed_settings.py

# 5. Створити адміністратора (вручну, дивись розділ нижче)
```

### Розробка — корисні команди

```bash
# Перезапустити веб після змін у Python/HTML
docker compose restart web

# Перебілдити після змін у requirements.txt або Dockerfile
docker compose build web && docker compose up -d

# Логи в реальному часі
docker compose logs -f web

# Логи тільки помилки
docker compose logs web | grep -i error
```

---

## Міграції БД

Міграції запускаються **автоматично** при старті контейнера.

Якщо потрібно запустити вручну:

```bash
docker compose exec web flask db upgrade
```

Застосувати конкретну ревізію:

```bash
docker compose exec web flask db upgrade <revision_id>
```

Переглянути поточний стан:

```bash
docker compose exec web flask db current
docker compose exec web flask db history
```

---

## Створення користувачів

### Адмін або менеджер

```bash
docker compose exec web python -c "
from app import create_app
from app.extensions import db
from app.models.user import User
app = create_app()
with app.app_context():
    u = User(username='admin', email='admin@admin.com', user_type='admin', is_active=True)
    u.set_password('admin')
    db.session.add(u)
    db.session.commit()
    print('Створено:', u.username)
"
```

Для менеджера — змінити `user_type='manager'`.

### Флорист

```bash
docker compose exec web python -c "
from app import create_app
from app.extensions import db
from app.models.user import User
app = create_app()
with app.app_context():
    u = User(username='florist', email='florist@florist.com', user_type='florist', is_active=True)
    u.set_password('florist123')
    db.session.add(u)
    db.session.commit()
    print('Створено:', u.username)
"
```

Флорист бачить тільки сторінку `/florist` — список доставок для збирання букетів.

---

## Видалення БД і чистий старт

> БД зберігається в папці `./data/postgres` (bind mount, не docker volume).

```bash
# 1. Зупинити контейнери
docker compose down

# 2. Видалити дані БД
rm -rf data/postgres

# 3. Запустити заново (міграції застосуються автоматично)
docker compose up -d

# 4. Заповнити довідники
docker compose exec web python scripts/seed_settings.py
```

Одним блоком:

```bash
docker compose down && rm -rf data/postgres && docker compose up -d
```

---

## Бекап і відновлення БД

### Створити бекап

```bash
docker compose exec web python scripts/database_backup.py backup
```

Файл збережеться в папку `backups/` з timestamp у назві, наприклад:
`backups/kvitkova_crm_2026-03-24_15-30-00.sql`

Або через `pg_dump` напряму:

```bash
docker compose exec postgres pg_dump -U kvitkova_user kvitkova_crm > backups/backup_$(date +%Y-%m-%d).sql
```

### Відновити з бекапу

```bash
# Зупинити веб (щоб не було активних з'єднань)
docker compose stop web telegram-bot

# Відновити
docker compose exec -T postgres psql -U kvitkova_user kvitkova_crm < backups/backup_2026-03-24.sql

# Запустити веб назад
docker compose start web telegram-bot
```

Або через скрипт:

```bash
docker compose exec web python scripts/database_backup.py restore backups/backup_2026-03-24.sql
```

---

## Імпорт клієнтів з CSV

Доступні два типи імпорту за адресою `/import`:

| Маршрут | Опис |
|---------|------|
| `/import` | Стандартний імпорт (базовий формат) |
| `/import/operational` | Операційний CSV (формат відвантажень) |
| `/import/kvitkovapovnya` | Операційна Квіткова Повня 2026 |

**Формат Квіткова Повня 2026** — колонки: `Name of clients`, `Ім'я на кого доставка`, `Вид підписки`, `Коли відправка`, `Розмір`, `Місто`, `Адреса`, `Коментар до адреси`, `Номер телефону отримувача`, `Планова доставка`, `№ доставки`, `Відсоток знижки`, `Для кого`, `Відмітка якщо весільна`.

Логіка за колонкою `№ доставки`:
- Порожньо → тільки клієнт (без замовлення)
- `0` → разове замовлення
- `1` → підписка + 4 доставки
- `2` → підписка + 3 доставки
- `3` → підписка + 2 доставки
- `4` → підписка + 1 доставка
- `5` → підписка + 1 доставка + позначка "потрібно продовжити" (з'являється в дашборді)

---

## Сторінки системи

| URL | Доступ | Опис |
|-----|--------|------|
| `/` | admin, manager | Дашборд |
| `/orders` | admin, manager | Замовлення |
| `/subscriptions` | admin, manager | Підписки |
| `/clients` | admin, manager | Клієнти |
| `/deliveries` | admin, manager | Доставки |
| `/couriers` | admin, manager | Кур'єри |
| `/routes` | admin, manager | Маршрути та призначення кур'єрів |
| `/route-generator` | admin, manager | Генератор маршрутів |
| `/reports` | admin, manager | Звіти |
| `/certificates` | admin, manager | Сертифікати |
| `/transactions` | admin, manager | Транзакції / списання |
| `/import` | admin | Імпорт CSV |
| `/florist` | florist | Збирання букетів |
| `/settings` | admin | Налаштування |

---

## Структура проекту

```
app/
├── blueprints/          # Route handlers (один blueprint = один розділ)
│   ├── auth/            # /auth/login, /auth/logout
│   ├── clients/         # /clients
│   ├── orders/          # /orders
│   ├── subscriptions/   # /subscriptions
│   ├── couriers/        # /couriers
│   ├── certificates/    # /certificates
│   ├── dashboard/       # / (дашборд)
│   ├── routes/          # /routes, /route-generator
│   ├── florist/         # /florist
│   ├── reports/         # /reports
│   ├── settings/        # /settings
│   ├── transactions/    # /transactions
│   └── import_csv/      # /import
├── models/              # SQLAlchemy моделі
├── services/            # Бізнес-логіка
├── templates/           # Jinja2 шаблони
└── static/              # CSS, JS

migrations/versions/     # Alembic міграції
scripts/                 # Адміністративні скрипти
```

---

## Основні таблиці БД

| Таблиця | Опис |
|---------|------|
| `user` | Користувачі (admin, manager, florist) |
| `client` | Клієнти |
| `subscription` | Підписки (Weekly, Monthly, Bi-weekly) |
| `order` | Замовлення |
| `delivery` | Доставки (дата, статус, кур'єр) |
| `courier` | Кур'єри + telegram_chat_id |
| `delivery_routes` | Збережені маршрути |
| `route_deliveries` | Зупинки маршруту |
| `certificates` | Сертифікати |
| `transaction` | Транзакції та списання |
| `recipient_phone` | Додаткові телефони отримувача |

---

## Telegram бот

Кур'єр отримує маршрут через Telegram з кнопками **Прийняти / Відхилити**.
Після прийняття — повний список адрес, отримувачів та телефонів.

Для роботи бота потрібно задати `TELEGRAM_BOT_TOKEN` в `.env`.
