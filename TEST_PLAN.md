# Test Plan — CRM Kvitkova Povnya

Три рівні покриття: **unit** (чиста логіка без БД), **service** (логіка з БД через SQLite in-memory),
**integration/HTTP** (Flask test client, повний request–response цикл).

Smoke-тести на PostgreSQL виділені окремо — SQLite не ловить частину різниць у типах та constraint-ах.

---

## Рівень 1: Unit (models / pure functions)

### 1.1 `Certificate` — методи моделі

| # | Тест | Метод |
|---|------|-------|
| U01 | `effective_status()` → `'active'` якщо status='active' і expires_at >= today | unit |
| U02 | `effective_status()` → `'expired'` якщо expires_at < today (status='active') | unit |
| U03 | `effective_status()` → `'used'` якщо status='used', незалежно від expires_at | unit |
| U04 | `value_display()` → `'500 грн'` для type='amount', value_amount=500 | unit |
| U05 | `value_display()` → `'M'` для type='size', value_size='M' | unit |
| U06 | `value_display()` → `'Підписка / L'` для type='subscription', value_size='L' | unit |
| U07 | `value_display()` → `'Підписка'` для type='subscription', value_size=None | unit |
| U08 | `type_display()` → коректна мітка для кожного з 3 типів | unit |
| U09 | `is_active()` → True якщо status='active' і не прострочений | unit |
| U10 | `is_active()` → False якщо прострочений | unit |

### 1.2 `generate_certificate_code()`

| # | Тест | Метод |
|---|------|-------|
| U11 | Перший сертифікат type='amount' → `'Р0001'` | unit+db |
| U12 | Перший сертифікат type='subscription' → `'П0001'` | unit+db |
| U13 | Наступний після `'Р0003'` → `'Р0004'` | unit+db |
| U14 | Некоректний суфікс в останньому коді → fallback до num=1 | unit |

### 1.3 `User` — ролі та дозволи

| # | Тест | Метод |
|---|------|-------|
| U15 | `check_password()` → True для правильного пароля | unit |
| U16 | `check_password()` → False для неправильного пароля | unit |
| U17 | `has_role('admin')` → True/False залежно від призначених ролей | unit |
| U18 | `has_permission('view_reports')` → True для admin, False для manager | unit |
| U19 | `has_permission('edit_settings')` → True для admin, False для manager | unit |
| U20 | Florist user (user_type='florist') → не має жодної ролі ROLE_ADMIN/ROLE_MANAGER | unit |

### 1.4 `order_service` — чисті функції (без DB)

| # | Тест | Метод |
|---|------|-------|
| U21 | `detect_order_scenario()` → `'subscription'` для Weekly/Monthly/Bi-weekly | unit |
| U22 | `detect_order_scenario()` → `'order'` для One-time або порожнього delivery_type | unit |
| U23 | `detect_order_scenario()` → пріоритет явного `order_scenario` поля | unit |
| U24 | `resolve_delivery_type()` → scenario='order', порожньо → `'One-time'` | unit |
| U25 | `resolve_delivery_type()` → scenario='subscription', порожньо → `'Monthly'` | unit |
| U26 | `resolve_delivery_type()` → scenario='subscription', raw='Weekly' → `'Weekly'` | unit |
| U27 | `calculate_next_delivery_date()` Weekly → +7 днів, корегується до потрібного дня тижня | unit |
| U28 | `calculate_next_delivery_date()` Bi-weekly → +14 днів, корегується до потрібного дня | unit |
| U29 | `calculate_next_delivery_date()` Monthly → +28 днів, найближчий потрібний день тижня | unit |
| U30 | `build_delivery_dates()` для One-time → рівно 1 дата | unit |
| U31 | `build_delivery_dates()` для Weekly → рівно 4 дати, всі унікальні | unit |
| U32 | `build_delivery_dates()` для Monthly → 4 дати, всі в межах розумного інтервалу | unit |
| U33 | `build_delivery_dates()` з датою 31 грудня → не падає | unit |
| U34 | `paginate_orders()` → коректна розбивка сторінок | unit |

### 1.5 `reports_service` — чисті функції

| # | Тест | Метод |
|---|------|-------|
| U35 | `_label_key('')` → `'__unspecified__'` | unit |
| U36 | `_label_key('—')` → `'__unspecified__'` | unit |
| U37 | `_label_key('Не вказано')` → `'__unspecified__'` | unit |
| U38 | `_label_key('Instagram')` → `'instagram'` (lowercase) | unit |
| U39 | `_display_label('')` → `'Не вказано'` | unit |
| U40 | `_display_label('Instagram')` → `'Instagram'` (збережений регістр) | unit |
| U41 | `_rows_to_items()` → об'єднує різні варіанти "не вказано" в один bucket | unit |
| U42 | `_rows_to_items()` → сортує за спаданням count | unit |
| U43 | `_parse_month('2025-03')` → `date(2025, 3, 1)` | unit |
| U44 | `_parse_month('')` → поточний місяць | unit |
| U45 | `_parse_month('invalid')` → поточний місяць (без падіння) | unit |
| U46 | `_month_bounds()` → коректні межі для грудня (→ 1 січня наступного року) | unit |

### 1.6 `florist` — `_build_subscription_delivery_index()`

| # | Тест | Метод |
|---|------|-------|
| U47 | Порожній список order_ids → повертає `{}` | unit |
| U48 | Доставки одного замовлення нумеруються 1,2,3,4 | unit+db |
| U49 | Скасовані доставки ('Скасовано') не враховуються в нумерації | unit+db |
| U50 | Доставки різних замовлень нумеруються незалежно | unit+db |

### 1.7 `delivery_service` — чисті функції

| # | Тест | Метод |
|---|------|-------|
| U51 | `get_financial_week_dates(offset=0)` → субота–п'ятниця поточного тижня | unit |
| U52 | `get_financial_week_dates(offset=1)` → наступний тиждень | unit |
| U53 | `group_deliveries_by_date()` → групує правильно, ключі — дати | unit |

---

## Рівень 2: Service (DB logic, SQLite in-memory)

### 2.1 `client_service`

| # | Тест |
|---|------|
| S01 | `create_client()` → успіх з тільки instagram |
| S02 | `create_client()` → instagram нормалізується (прибирається `@`) |
| S03 | `create_client()` → помилка якщо instagram порожній |
| S04 | `create_client()` → помилка дубліката instagram (case-insensitive) |
| S05 | `create_client()` → помилка дубліката instagram з `@` vs без `@` |
| S06 | `create_client()` → помилка дубліката telegram |
| S07 | `create_client()` → помилка дубліката phone |
| S08 | `create_client()` → помилка невалідного телефону (не `+380XXXXXXXXX`) |
| S09 | `create_client()` → телефон `+380671234567` проходить валідацію |
| S10 | `update_client()` → зміна даних без конфліктів |
| S11 | `update_client()` → помилка якщо новий instagram конфліктує з ІНШИМ клієнтом |
| S12 | `update_client()` → НЕ помилка якщо той самий instagram для ТОГО ж клієнта |
| S13 | `update_client()` → НЕ помилка якщо той самий telegram для ТОГО ж клієнта |

### 2.2 `order_service` (з DB)

| # | Тест |
|---|------|
| S14 | `create_order_and_deliveries()` → Order та Delivery записи зберігаються в БД |
| S15 | `create_order_and_deliveries()` → підписка Weekly створює рівно 4 Delivery |
| S16 | `create_order_and_deliveries()` → One-time створює рівно 1 Delivery |
| S17 | `create_order_and_deliveries()` → is_pickup=True → street='Самовивіз' в Order і Delivery |
| S18 | `create_order_and_deliveries()` → перший Delivery має time_from/time_to, решта — None |
| S19 | `create_order_and_deliveries()` → перший Delivery має comment з order, решта — порожній |
| S20 | `create_order_and_deliveries()` → всі Delivery мають status='Очікує' |
| S21 | `create_order_and_deliveries()` → extend_from_order_id → позначає попереднє замовлення як продовжене |
| S22 | `get_or_create_client()` → повертає клієнта якщо instagram знайдено |
| S23 | `get_or_create_client()` → помилка якщо клієнт не знайдений |
| S24 | `update_order()` → оновлює Order та синхронізує активні Delivery |
| S25 | `update_order()` → НЕ змінює Delivery зі статусами 'Доставлено'/'Скасовано' |
| S26 | `update_order()` → зміна клієнта через новий instagram |
| S27 | `update_order()` → помилка якщо новий instagram не існує |
| S28 | `delete_order()` → видаляє Order, всі Delivery та RouteDelivery |
| S29 | `get_orders()` → пошук через `q` по instagram, recipient_name (ilike) |
| S30 | `get_orders()` → фільтр по city, delivery_type, size |
| S31 | `get_orders()` → фільтр по date_from/date_to через Delivery.delivery_date |
| S32 | `get_orders()` → некоректна дата в date_from → не падає, ігнорується |

### 2.3 Сценарій продовження підписки

| # | Тест |
|---|------|
| S33 | Нове замовлення з extend_from_order_id → попереднє Order.is_subscription_extended=True |
| S34 | Нове замовлення з extend_from_order_id → subscription_followup_status='extended' |
| S35 | Якщо попереднє замовлення вже extended → повторне продовження не скидає статус |

### 2.4 `delivery_service` (з DB)

| # | Тест |
|---|------|
| S36 | `set_delivery_status()` → оновлює статус та status_changed_at |
| S37 | `set_delivery_status()` → Розподілено→Доставлено → courier.deliveries_count збільшується на 1 |
| S38 | `set_delivery_status()` → перший перехід на Доставлено → delivered_at заповнюється |
| S39 | `set_delivery_status()` → повторний перехід на Доставлено → delivered_at не перезаписується |
| S40 | `update_delivery()` → оновлює поля delivery |
| S41 | `update_delivery()` → custom_amount оновлюється в Order якщо size='Власний' |
| S42 | `update_delivery()` → custom_amount НЕ оновлюється якщо size != 'Власний' |
| S43 | `assign_courier_to_deliveries()` → Delivery отримує courier_id і статус 'Розподілено' |
| S44 | `get_deliveries()` → фільтр по financial_week включає субота–п'ятниця |
| S45 | `get_deliveries()` → фільтр по date_from/date_to |
| S46 | `get_deliveries()` → фільтр по client_instagram |
| S47 | `get_deliveries()` → некоректна дата → не падає |

### 2.5 `reports_service` (з DB)

| # | Тест |
|---|------|
| S48 | `get_reports_data()` → marketing_all_total >= marketing_month_total (всі >= місяць) |
| S49 | `get_reports_data()` → for_whom_all_total >= for_whom_month_total |
| S50 | `get_reports_data()` → різні варіанти "не вказано" зливаються в один запис 'Не вказано' |
| S51 | `get_reports_data()` → marketing_all містить всі унікальні джерела (без дублів) |
| S52 | `get_reports_data()` → monthly_orders_total >= monthly_subscriptions_total |
| S53 | `_monthly_orders_trend()` → порожня БД → порожні списки, без падіння |
| S54 | `get_reports_data()` → selected_month фільтрує тільки замовлення обраного місяця |

---

## Рівень 3: Integration/HTTP (Flask test client)

### 3.1 Auth

| # | Тест |
|---|------|
| I01 | `GET /auth/login` → 200 для неавторизованого |
| I02 | `POST /auth/login` → редирект на dashboard при правильних даних (admin/manager) |
| I03 | `POST /auth/login` → редирект на `/florist` при правильних даних (florist user_type) |
| I04 | `POST /auth/login` → 200 + flash при невірному паролі |
| I05 | `GET /auth/logout` → редирект на login |
| I06 | Будь-який protected маршрут без авторизації → редирект на `/auth/login` |

### 3.2 Roles / Access Control

| # | Тест |
|---|------|
| I07 | Florist user: `GET /florist` → 200 |
| I08 | Florist user: `GET /orders` → редирект або 403 (не admin/manager маршрут) |
| I09 | Florist user: `GET /reports` → редирект або 403 |
| I10 | Admin user: `GET /florist` → 200 (admin може дивитись florist view) |
| I11 | Admin user: `GET /reports` → 200 |
| I12 | Manager user: `GET /reports` → 403 або редирект (немає view_reports) |

### 3.3 Certificates routes

| # | Тест |
|---|------|
| I13 | `GET /certificates` → 200, counts у контексті |
| I14 | `GET /certificates?status=active` → тільки активні в таблиці |
| I15 | `GET /certificates?status=expired` → і expired і active+прострочена дата |
| I16 | `GET /certificates/generate-code?type=amount` → JSON з кодом `Р000X` |
| I17 | `GET /certificates/generate-code?type=subscription` → JSON з кодом `П000X` |
| I18 | `POST /certificates/create` → 200 + success=True з валідними даними type=amount |
| I19 | `POST /certificates/create` → 400 + errors якщо code вже існує |
| I20 | `POST /certificates/create` → 400 якщо value_amount <= 0 |
| I21 | `POST /certificates/create` → 400 якщо value_size порожній для type=size |
| I22 | `POST /certificates/create` → expires_at = today + 1 рік (перевірка в БД) |
| I23 | `POST /certificates/validate` → valid=True для активного сертифіката |
| I24 | `POST /certificates/validate` → error для невідомого коду |
| I25 | `POST /certificates/validate` → error для status='used' |
| I26 | `POST /certificates/validate` → error для простроченого |

### 3.4 Clients routes

| # | Тест |
|---|------|
| I27 | `GET /clients` → 200 |
| I28 | `GET /clients?q=test` → пошук по instagram |
| I29 | `GET /clients?sub=active` → тільки клієнти з підписками |
| I30 | `POST /clients/new` → 200 + success=True |
| I31 | `POST /clients/new` → 400 + type='duplicate' при дублікаті |
| I32 | `POST /clients/<id>` → 200 + success=True при оновленні |
| I33 | `POST /clients/<id>/delete` → 200 якщо немає Delivery |
| I34 | `POST /clients/<id>/delete` → 400 якщо є Delivery |
| I35 | `GET /clients/json` → JSON масив клієнтів |

### 3.5 Orders routes

| # | Тест |
|---|------|
| I36 | `GET /orders` → 200 |
| I37 | `POST /orders/new` → створення одноразового замовлення → redirect + Delivery в БД |
| I38 | `POST /orders/new` → підписка Weekly → 4 Delivery в БД |
| I39 | `POST /orders/new` з валідним certificate_code → сертифікат status='used' після |
| I40 | `POST /orders/new` з простроченим certificate_code → 400/помилка |
| I41 | `POST /orders/new` з використаним certificate_code → 400/помилка |
| I42 | `POST /orders/<id>/edit` → оновлення збережено |
| I43 | `POST /orders/<id>/delete` → Order і Delivery видалені |

### 3.6 Couriers routes

| # | Тест |
|---|------|
| I44 | `POST /couriers/new` (JSON) → 200 + courier в response |
| I45 | `POST /couriers/new` → 400 якщо phone вже існує |
| I46 | `POST /couriers/new` → 400 якщо name або phone порожні |
| I47 | `POST /couriers/<id>/toggle` → active перемикається |
| I48 | `POST /couriers/<id>/delete` → 200 якщо немає активних доставок |
| I49 | `POST /couriers/<id>/delete` → 400 якщо є доставки зі статусом Очікує/Розподілено |
| I50 | `POST /couriers/<id>/edit` → name та phone оновлені |
| I51 | `POST /couriers/<id>/edit` → 400 якщо phone конфліктує з іншим кур'єром |
| I52 | `POST /couriers/<id>/reset-telegram` → всі telegram поля = None/False |

### 3.7 Florist routes

| # | Тест |
|---|------|
| I53 | `GET /florist` → 200, передає subscription_delivery_index |
| I54 | `GET /florist?date=2025-06-15` → доставки за обрану дату |
| I55 | `POST /florist/deliveries/status` з status_key='assembled' → florist_status='Зібрано' |
| I56 | `POST /florist/deliveries/status` з status_key='handoff' → florist_status="Передано кур'єру" + delivery.status='Розподілено' |
| I57 | `POST /florist/deliveries/status` з status_key='delivered' → delivery.status='Доставлено' + delivered_at заповнюється |
| I58 | `POST /florist/deliveries/status` → скасовані доставки ігноруються (updated_count не рахує їх) |
| I59 | `POST /florist/deliveries/status` → 400 якщо status_key невалідний |
| I60 | `POST /florist/deliveries/status` → 400 якщо delivery_ids порожній |

### 3.8 Reports route

| # | Тест |
|---|------|
| I61 | `GET /reports` → 200 |
| I62 | `GET /reports?month=2025-03` → selected_month='2025-03' в контексті |
| I63 | `GET /reports?month=invalid` → 200 без падіння, обирається поточний місяць |

---

## Рівень 4: Transaction Safety

| # | Тест |
|---|------|
| T01 | Якщо `db.session.commit()` падає після `db.session.add(order)` — Order НЕ збережено (rollback) |
| T02 | `delete_order()` — якщо видалення Delivery падає — Order теж НЕ видалено (атомарність) |
| T03 | Позначення сертифіката 'used' + create order — якщо Order не збережено — сертифікат лишається 'active' |
| T04 | `assign_courier_to_deliveries()` → якщо одне призначення падає → решта не застосовані (rollback) |
| T05 | `set_delivery_status()` → courier.deliveries_count оновлюється в тій же транзакції що і delivery.status |

---

## Рівень 5: DB Constraints (PostgreSQL smoke tests)

> Запускати окремо проти реального PostgreSQL. SQLite не перевіряє FK, унікальність по-іншому.

| # | Тест |
|---|------|
| P01 | Вставка Certificate з дублікатом code → `IntegrityError` (UNIQUE constraint) |
| P02 | Вставка Client з дублікатом instagram → `IntegrityError` |
| P03 | Вставка Client з дублікатом phone → `IntegrityError` |
| P04 | Вставка Certificate з неіснуючим order_id → `IntegrityError` (FK) |
| P05 | Вставка Delivery з неіснуючим client_id → `IntegrityError` (FK) |
| P06 | Видалення Client з існуючими Delivery → `IntegrityError` або handled error |
| P07 | `Certificate.value_amount` типу Numeric(10,2) → зберігає дробові значення коректно |
| P08 | Case-insensitive пошук instagram через `func.lower()` → працює на PG як очікується |
| P09 | `ilike` в `get_orders()` → повертає результат незалежно від регістру |
| P10 | `Order.created_at` з `db.func.now()` → зберігається з часовою зоною коректно |

---

## Загальна статистика

| Рівень | Кількість тестів |
|--------|-----------------|
| Unit (U) | 53 |
| Service (S) | 54 |
| Integration (I) | 61 |
| Transaction Safety (T) | 5 |
| PostgreSQL Smoke (P) | 10 |
| **Всього** | **183** |

---

## Нотатки по інфраструктурі

- **Unit / Service / Integration**: SQLite in-memory (`sqlite:///:memory:`), CSRF вимкнений
- **Transaction Safety**: SQLite з перехопленням exceptions через `unittest.mock.patch`
- **PostgreSQL Smoke**: окремий pytest marker `@pytest.mark.postgres`, запускати через `pytest -m postgres`
- **Fixtures**: `admin_user`, `manager_user`, `florist_user`, `client`, `order`, `certificate` — переносні між усіма рівнями
- **Конфігурація тестів**: `app/config.py` клас `Testing` → `TESTING=True`, `WTF_CSRF_ENABLED=False`
