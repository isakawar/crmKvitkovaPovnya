# Performance Plan — CRM Kvitkova Povnya

> Аналіз вузьких місць при навантаженні ~100 замовлень/день (36 500+/рік).
> Пріоритети розставлені від критичного до помірного.

---

## Критичні проблеми (виправити до prod)

### 1. `assign_deliveries()` скидає ВСІ доставки в БД

**Файл:** `app/services/delivery_service.py` ~line 146

```python
# Зараз — катастрофа при масштабі
for d in Delivery.query.all():  # 100 замовлень × 4 доставки × 365 днів = 146 000 рядків
    d.courier_id = None
    d.status = 'Очікує'
```

**Проблема:** При кожному розподілі кур'єрів завантажується вся таблиця `delivery` за весь час і виконується масовий UPDATE. Через рік — зависне на кілька секунд або timeout.

**Рішення:** Фільтрувати тільки доставки конкретної дати:
```python
target_date = date.today()
deliveries = Delivery.query.filter(Delivery.delivery_date == target_date).all()
```

---

### 2. `get_all_clients()` — Python-пагінація замість DB

**Файли:** `app/services/client_service.py:6`, `app/blueprints/clients/routes.py:16`

```python
# Зараз — всі клієнти в RAM на кожен GET /clients
all_clients = Client.query.all()
# потім в Python:
all_clients = [c for c in all_clients if query in c.name]
clients_on_page = all_clients[start_idx:end_idx]
```

**Проблема:** При 1000+ клієнтах — кожен перегляд сторінки `/clients` вивантажує всю таблицю в пам'ять сервера. Пошук і пагінація виконуються в Python, а не в PostgreSQL.

**Рішення:** Перенести фільтрацію і пагінацію на рівень DB:
```python
query = Client.query
if search:
    query = query.filter(func.lower(Client.name).contains(search.lower()))
clients = query.order_by(Client.id.desc()).paginate(page=page, per_page=20)
```

---

## Серйозні проблеми (виправити протягом першого місяця)

### 3. Відсутні DB індекси на ключових колонках

**Файли:** всі моделі в `app/models/`

Жоден `index=True` не проставлений. Всі фільтри — повні скани таблиць.

| Колонка | Де використовується | Пріоритет |
|---------|---------------------|-----------|
| `delivery.delivery_date` | флорист, маршрути, всі фільтри | Критичний |
| `delivery.status` | фільтри скрізь | Критичний |
| `delivery.courier_id` | розподіл кур'єрів | Критичний |
| `order.client_id` | JOIN при get_orders | Високий |
| `order.delivery_type` | підписки, звіти | Високий |
| `client.instagram` | пошук, `func.lower()` | Середній |
| `certificate.status` | фільтри списку | Середній |

**Рішення:** Додати `index=True` до колонок або окремі `db.Index(...)`:
```python
# delivery.py
delivery_date = db.Column(db.Date, nullable=False, index=True)
status = db.Column(db.String(50), index=True)
courier_id = db.Column(db.Integer, db.ForeignKey('courier.id'), index=True)

# order.py
client_id = db.Column(db.Integer, db.ForeignKey('client.id'), index=True)
```

---

### 4. N+1 запити в шаблонах

**Файли:** `app/templates/certificates/list.html:127`, шаблони замовлень

```jinja2
{# Для кожного сертифіката — окремий SELECT order, потім SELECT client #}
{{ cert.order.client.instagram }}
```

При 50 сертифікатів → 100 прихованих запитів на одне завантаження сторінки.

**Рішення:** `joinedload` в route:
```python
certs = Certificate.query\
    .options(joinedload(Certificate.order).joinedload(Order.client))\
    .all()
```

Аналогічно для `get_orders()` — додати `joinedload(Order.client)` і `joinedload(Order.deliveries)`.

---

### 5. `_monthly_orders_trend()` росте нескінченно

**Файл:** `app/services/reports_service.py` ~line 128

```python
# Зараз — всі замовлення за весь час
db.session.query(Order.created_at, Order.delivery_type)
    .filter(Order.created_at.isnot(None))
    .order_by(Order.created_at.asc())
    .all()
```

**Проблема:** При 36 500 замовлень/рік цей запит завантажує все в пам'ять і зростає щомісяця.

**Рішення:** Обмежити вибірку останніми 12 місяцями:
```python
from datetime import datetime, timedelta
cutoff = datetime.utcnow() - timedelta(days=365)
.filter(Order.created_at >= cutoff)
```

---

### 6. `get_orders()` — JOIN без індексу по даті

**Файл:** `app/services/order_service.py` ~line 198

```python
query = query.join(Delivery)
query = query.filter(Delivery.delivery_date >= parsed_date_from)
```

JOIN таблиці `delivery` без індексу на `delivery_date` — sequential scan при фільтрі по діапазону дат. Вирішується додаванням індексу (див. пункт 3).

---

## Помірні проблеми (виправити при нагоді)

### 7. Звітна сторінка — 8 важких запитів без кешування

**Файл:** `app/services/reports_service.py` — `get_reports_data()`

8 окремих GROUP BY запитів при кожному завантаженні `/reports`. Без будь-якого кешування.

**Рішення:** Flask-Caching з TTL 5 хвилин:
```python
from flask_caching import Cache
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})

@cache.cached(timeout=300, key_prefix='reports_data_%s')
def get_reports_data(period):
    ...
```

---

### 8. `active_sub_client_ids` — зайвий запит на кожен `/clients`

**Файл:** `app/blueprints/clients/routes.py` ~line 18

```python
# Виконується завжди, навіть коли sub_filter не потрібен
active_sub_client_ids = set(
    row[0] for row in db.session.query(Order.client_id)
    .filter(Order.delivery_type.in_([...]))
    .distinct().all()
)
```

**Рішення:** Обгорнути в умову:
```python
if sub_filter:
    active_sub_client_ids = set(...)
else:
    active_sub_client_ids = set()
```

---

### 9. `florist_bulk_update_status()` без rollback

**Файл:** `app/blueprints/florist/routes.py` ~line 91

Якщо `commit()` впаде після часткового оновлення — частина доставок буде зі старим статусом, частина з новим. Немає `try/except` з `db.session.rollback()`.

**Рішення:**
```python
try:
    # ... оновлення
    db.session.commit()
except Exception as e:
    db.session.rollback()
    return jsonify({'success': False, 'error': str(e)}), 500
```

---

## Зведена таблиця пріоритетів

| # | Проблема | Файл | Пріоритет | Складність |
|---|----------|------|-----------|------------|
| 1 | `assign_deliveries()` повний скан | delivery_service.py | Критичний | Низька |
| 2 | `get_all_clients()` Python-пагінація | client_service.py | Критичний | Середня |
| 3 | Відсутні DB індекси | всі моделі | Критичний | Низька |
| 4 | N+1 запити в шаблонах | routes + templates | Високий | Середня |
| 5 | `_monthly_orders_trend()` без ліміту | reports_service.py | Високий | Низька |
| 6 | JOIN без індексу в get_orders | order_service.py | Високий | Низька (вирішується п.3) |
| 7 | Звіти без кешування | reports_service.py | Середній | Середня |
| 8 | Зайвий запит `active_sub_client_ids` | clients/routes.py | Низький | Низька |
| 9 | Немає rollback у florist | florist/routes.py | Середній | Низька |

---

## Швидкий виграш (можна зробити за 1-2 години)

1. Додати `index=True` до `delivery_date`, `status`, `courier_id`, `order.client_id`
2. Фільтр по даті в `assign_deliveries()`
3. Обмежити `_monthly_orders_trend()` 12 місяцями
4. Умовний `active_sub_client_ids`
5. `try/except rollback` у florist bulk update
