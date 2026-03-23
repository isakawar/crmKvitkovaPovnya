# CLAUDE.md — CRM Kvitkova Povnya

## Про проект

Flask CRM для квіткового магазину "Kvitkova Povnya". Управління клієнтами, замовленнями, підписками на букети, доставками, кур'єрами та маршрутами. Інтеграція з Telegram-ботом для кур'єрів.

---

## Стек

- **Backend:** Python / Flask
- **ORM:** Flask-SQLAlchemy (SQLAlchemy)
- **БД:** PostgreSQL 15
- **Міграції:** Flask-Migrate / Alembic
- **Автентифікація:** Flask-Login
- **Шаблони:** Jinja2
- **CSS:** Tailwind CSS v3 (компілюється через `npm run build`)
- **UI компоненти:** Bootstrap 5.3.2 + Bootstrap Icons
- **WSGI:** Gunicorn (production)
- **Telegram:** python-telegram-bot 20.7
- **Планувальник:** APScheduler

---

## Запуск

### Локально (без Docker)
```bash
python run.py  # http://localhost:5055, debug=True
```

### Docker (production-подібний режим)
```bash
docker compose up
# Web: http://localhost:8002
```

### Tailwind CSS
```bash
npm run dev    # watch-режим під час розробки
npm run build  # production build (мінімізований)
```
Вхід: `app/static/css/src/input.css` → вихід: `app/static/css/main.css`

---

## Структура проекту

```
app/
├── __init__.py          # Flask app factory (create_app)
├── extensions.py        # db, migrate, login_manager
├── config.py            # Dev/Prod/Testing конфіги
├── blueprints/          # Route handlers
│   ├── auth/            # /auth/login, /auth/logout
│   ├── orders/          # /orders, /orders/new, /subscriptions
│   ├── clients/         # /clients
│   ├── couriers/        # /couriers
│   ├── certificates/    # /certificates
│   ├── dashboard/       # / (головна)
│   ├── routes/          # /routes, /route-generator
│   ├── florist/         # /florist (окрема роль)
│   ├── reports/         # /reports
│   ├── settings/        # /settings
│   └── import_csv/      # /import
├── models/
│   ├── order.py         # Order (таблиця "order")
│   ├── delivery.py      # Delivery (таблиця "delivery")
│   ├── client.py        # Client (таблиця "client")
│   ├── courier.py       # Courier (таблиця "courier")
│   ├── certificate.py   # Certificate (таблиця "certificates")
│   ├── delivery_route.py# DeliveryRoute, RouteDelivery
│   ├── price.py         # Price (таблиця "prices")
│   ├── settings.py      # Settings (таблиця "settings")
│   └── user.py          # User, Role (таблиці "user", "roles")
├── services/
│   ├── order_service.py         # Основна бізнес-логіка замовлень
│   ├── delivery_service.py      # Групування доставок
│   ├── client_service.py        # CRUD клієнтів
│   ├── courier_service.py       # Створення кур'єрів
│   ├── route_optimizer_service.py # Зовнішній API оптимізації
│   ├── csv_import_service.py    # Імпорт CSV
│   └── reports_service.py       # Звіти
├── templates/
│   ├── layout.html              # Базовий шаблон (sidebar, topbar)
│   ├── macros.html              # render_toast(), render_alerts()
│   ├── orders/
│   │   ├── _composer_modal.html # Modal створення замовлення/підписки
│   │   └── _composer_script.html# JS логіка composer modal (40KB)
│   └── certificates/
│       ├── list.html
│       └── _create_modal.html
├── static/
│   ├── css/src/input.css        # Tailwind вхід
│   ├── css/main.css             # Скомпільований CSS
│   └── js/clients.js
└── telegram_bot/                # Telegram бот для кур'єрів
```

---

## База даних

### Важливо: назви таблиць
SQLAlchemy за замовчуванням називає таблиці за класом у lowercase:
- `Order` → таблиця **`order`** (не `orders`)
- `User` → таблиця **`user`** (не `users`)
- `Client` → таблиця **`client`**
- `Delivery` → таблиця **`delivery`**
- `Certificate` → таблиця **`certificates`** (явно задано `__tablename__`)
- `DeliveryRoute` → таблиця **`delivery_routes`** (явно задано)

При написанні міграцій завжди перевіряй справжню назву таблиці.

### Запуск міграцій
Міграції запускаються автоматично при старті Docker (`entrypoint.sh`).
```bash
# Вручну в контейнері:
docker compose exec web flask db upgrade

# Або напряму в PostgreSQL:
docker compose exec postgres psql -U kvitkova_user -d kvitkova_crm
```

### Написання міграцій
Нова міграція — окремий файл у `migrations/versions/`. Дивись існуючі як зразок. При додаванні FK завжди перевіряй реальну назву таблиці (`order`, `user`, а не `orders`, `users`).

---

## Ключові концепції

### Підписки
Підписки — це **не окрема модель**, а замовлення (`Order`) з `delivery_type` в `('Weekly', 'Monthly', 'Bi-weekly')`. При створенні автоматично генерується 4 доставки. Підписка = тип + розмір (обидва поля обов'язкові).

### Сертифікати
Типи: `amount` (на суму грн), `size` (на розмір букету), `subscription` (на підписку = тип + розмір). Термін дії — автоматично 1 рік від дати створення. Статус: `active` → `used` (після використання в замовленні).

### Розміри замовлення
`S`, `M`, `L`, `XL`, `XXL`, `Власний` (потребує `custom_amount`).

### Ролі користувачів
- `admin` / `manager` — повний доступ
- `florist` — тільки `/florist` маршрути
- `courier` — тільки через Telegram бот

---

## Патерни коду

### Blueprint реєстрація
```python
# app/__init__.py
from app.blueprints.example import example_bp
app.register_blueprint(example_bp)

# app/blueprints/example/__init__.py
from flask import Blueprint
example_bp = Blueprint('example', __name__)
from app.blueprints.example import routes  # noqa
```

### AJAX ендпоінти
```python
# Всі AJAX запити перевіряємо через:
if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    return jsonify({'success': True, 'data': ...})

# Або для JSON body:
data = request.get_json()
return jsonify({'success': False, 'errors': [...]})
```

### Шаблони
- Всі шаблони розширюють `layout.html`
- Toast-нотифікації: `{{ render_toast() }}` + `{{ toast_script() }}` + `showToast('text', 'success'|'error')`
- Дати через фільтр: `{{ order.created_at | kyiv_time }}`
- CSS класи: `.order-*` для composer modal, `.order-panel`, `.order-field`, `.order-input`, `.order-label`

### Захист маршрутів
```python
from flask_login import login_required

@blueprint.route('/path')
@login_required
def view():
    ...
```
Глобальний захист всіх маршрутів реалізований у `before_request` в `app/__init__.py`.

---

## Tailwind CSS

Кастомні компоненти визначені в `app/static/css/src/input.css` через `@layer components`:
- `.order-*` — компоненти composer modal
- `.client-*` — компоненти клієнтського modal
- `.tag-*` — бейджі (розміри, типи)

**Після змін у шаблонах** що використовують нові Tailwind класи — потрібно перебілдити CSS:
```bash
npm run build
```
У Docker це не потрібно якщо класи вже є в скомпільованому `main.css`.

---

## Навігація (layout.html)

Sidebar навігація — рядки ~178-257 в `layout.html`. Паттерн для нового пункту:
```html
<a href="/path"
   class="flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors
          {% if request.path.startswith('/path') %}bg-amber-50 border border-amber-200 text-amber-700
          {% else %}text-stone-600 hover:bg-stone-200 hover:text-stone-900{% endif %}"
   title="Назва">
    <i class="bi bi-icon-name text-lg flex-shrink-0"></i>
    <span class="nav-label">Назва</span>
</a>
```

---

## Тести

```bash
pytest                    # всі тести
pytest tests/test_orders.py  # конкретний файл
```

Тести використовують SQLite in-memory БД (`sqlite:///:memory:`), CSRF вимкнений.

---

## Змінні середовища (.env)

```
DATABASE_URL=postgresql://kvitkova_user:password@postgres:5432/kvitkova_crm
TELEGRAM_BOT_TOKEN=...
DEPOT_ADDRESS=...          # адреса депо для оптимізації маршрутів
SECRET_KEY=...
ROUTE_OPTIMIZER_URL=...    # зовнішній API оптимізації маршрутів
```

---

## Корисні скрипти

```bash
# Наповнити БД початковими налаштуваннями (міста, розміри, типи доставки)
docker compose exec web python scripts/seed_settings.py

# Бекап БД
docker compose exec web python scripts/database_backup.py
```
