# CRM Kvitkova Povnya — Project Flow Documentation

Цей документ зібраний по фактичному коду проєкту (blueprints/services/models/templates) станом на 23.03.2026.

## 1) Архітектура і модулі

- Backend: Flask + SQLAlchemy + Alembic.
- UI: Jinja templates + Bootstrap/Tailwind.
- Головні доменні модулі:
  - `clients` — картки клієнтів.
  - `orders` — замовлення, підписки, shared composer modal, route-generator.
  - `routes` — збережені маршрути, призначення/відправка курʼєру.
  - `florist` — робоча сторінка флориста з bulk-статусами.
  - `dashboard` — операційні KPI і follow-up завершених підписок.
  - `reports` — аналітика джерел/типів/розмірів/тренду.
  - `settings` — довідники (міста, типи, розміри, for_whom, marketing_source, prices).
  - `certificates` — подарункові/підпискові сертифікати.

## 2) Ролі і доступ

Реалізація доступу зараз комбінована:

- Глобальний `before_request`:
  - неавторизовані редіректяться на `/auth/login`;
  - користувач `user_type='florist'` може працювати лише в `florist.*`.
- Додатково `@login_required` стоїть на більшості сторінок.
- `permission_required()` застосований у `settings`:
  - `/settings` вимагає `view_settings`;
  - `/settings/update` вимагає `edit_settings`.

Нюанс: частина CRUD-ендпоінтів (`/clients/*`, `/couriers/*`, частина `/settings/*`) не мають декоратора `@login_required`, але фактично закриті глобальним `before_request`.

## 3) Основні сутності (коротко)

- `Client`: `instagram`, `phone`, `telegram`, `credits`, `marketing_source`, `personal_discount`.
- `Order`: “шапка” оформлення (отримувач, місто/адреса, тип, розмір, графік, коментарі).
- `Delivery`: конкретна доставка (дата, статус, час, адресні поля, courier, florist_status).
- `DeliveryRoute` + `RouteDelivery`: збережений маршрут і його стопи.
- `Courier`: курʼєр + Telegram привʼязка.
- `Certificate`: сертифікати (`amount/size/subscription`, `active/used/expired`).
- `Settings`: довідники через `type/value`.
- `Price`: матриця цін `subscription_type x size`.

## 4) Головний бізнес-флоу: клієнт -> оформлення

### 4.1 Створення клієнта

Вхід: `POST /clients/new`.

Сервіс `create_client()`:

- `instagram` обовʼязковий.
- нормалізація: `@nickname` -> `nickname` (для збереження).
- валідація телефона: тільки `+380XXXXXXXXX`.
- перевірка унікальності:
  - instagram (case-insensitive, з урахуванням варіантів з/без `@`);
  - telegram (аналогічно);
  - phone (exact).

При дублікаті повертається структурована помилка:

- `type='duplicate'`
- `field` (`instagram|telegram|phone`)
- `client_id`
- текст “Відкрити його картку?”

### 4.2 Shared composer modal (єдиний flow для оформлення)

UI: `templates/orders/_composer_modal.html` + `templates/orders/_composer_script.html`.

Одна форма для двох режимів:

- `order` (разове замовлення, 1 доставка);
- `subscription` (цикл, 4 доставки).

Форма має hidden-поля:

- `order_scenario`
- `extend_from_order_id` (для продовження підписки).

### Сценарій визначається так

1. Якщо є валідний `order_scenario` (`order|subscription`) — він пріоритетний.
2. Інакше, якщо `delivery_type in ['Weekly','Monthly','Bi-weekly']` -> `subscription`.
3. Інакше -> `order`.

### Обовʼязкові поля при створенні

Базово:

- `client_instagram`, `recipient_name`, `recipient_phone`, `city`, `size`, `first_delivery_date`, `for_whom`.

Додатково:

- для `subscription`: `delivery_type`, `delivery_day`;
- якщо не самовивіз: `street`.

### Валідатори

- телефон отримувача: `+380XXXXXXXXX`;
- якщо `size='Власний'`: `custom_amount > 0`;
- optional certificate: існує, не used, не expired.

### 4.3 Створення Order + Delivery

Backend: `POST /orders/new` -> `create_order_and_deliveries()`.

Що відбувається:

1. Шукається клієнт по `client_instagram` (`get_or_create_client` у цьому контексті не створює, а лише знаходить).
2. Створюється `Order`.
3. Рахуються дати доставок:
   - `One-time` -> 1 дата;
   - `Weekly/Monthly/Bi-weekly` -> 4 дати.
4. Створюються `Delivery`:
   - підписка: 4 доставки;
   - разове: 1 доставка.

Ключове правило часу:

- `time_from/time_to` копіюється тільки в першу доставку;
- інші доставки створюються з `time_from=None`, `time_to=None`.

Коментар:

- `delivery.comment` для першої доставки = `order.comment`;
- для наступних доставок у циклі коментар порожній.

### 4.4 Режими доставки

В composer три режими:

- `courier` (адреса обовʼязкова),
- `nova_poshta` (використовується те саме текстове поле адреси, `delivery_method='nova_poshta'`),
- `pickup` (`is_pickup=True`, адресні поля для маршрутизації не використовуються).

## 5) Підписка: перегляд і продовження

### 5.1 Як система розуміє “це підписка”

Підписка = `order.delivery_type in ['Weekly', 'Monthly', 'Bi-weekly']`.

Окремої таблиці subscription немає; це `Order + набори Delivery`.

### 5.2 Детальна картка підписки

`GET /subscriptions/<order_id>` повертає JSON:

- client/recipient/delivery/notes/stats;
- масив доставок;
- related_orders (історія циклів для того ж клієнта+отримувача).

### 5.3 Поточний флоу продовження (UI-основний)

Кнопка “Продовжено” на Dashboard і кнопки з Subscription detail викликають composer API:

- `window.orderComposerApi.openSubscriptionExtension(orderId)`.

Composer робить:

1. `GET /orders/<id>/edit` (отримати prefill дані);
2. блокує перемикання сценарію в `subscription`;
3. ставить `data-extend-mode=true`;
4. заповнює всі поля;
5. очищає тільки `first_delivery_date` (його менеджер задає нову).

Після submit:

- іде стандартний `POST /orders/new`,
- передається `extend_from_order_id`,
- старий order позначається:
  - `is_subscription_extended=True`
  - `subscription_followup_status='extended'`
  - `subscription_followup_at=utcnow()`.

### 5.4 Legacy endpoint продовження

Є окремий `POST /orders/<id>/extend-subscription`, який:

- клонує order;
- автоматично обчислює `first_next_delivery` від останньої доставки;
- створює 4 нові доставки;
- також позначає старий order як extended.

У новому UI переважно використовується composer-flow, але legacy endpoint лишився робочим.

## 6) Редагування замовлення

`POST /orders/<id>/edit` -> `update_order()`.

Оновлює Order і синхронізує активні доставки:

- доставкам зі статусом `Доставлено` або `Скасовано` дані не переписуються;
- у майбутні/активні доставки копіюються address/phone/comment/preferences/delivery_method;
- дата першої активної доставки = новий `first_delivery_date`.

## 7) Операційний контур доставок

### 7.1 Список замовлень (`/orders`)

Сторінка рендерить deliveries, згруповані по датах (`group_deliveries_by_date`), з фільтрами:

- `q`, `city`, `delivery_type`, `size`, `date_from`, `date_to`.

Є bulk-оновлення часу/дати:

- `POST /orders/deliveries/time`
- можна оновити кілька доставок за раз;
- при зміні дати у вже `Розподілено` доставка відʼєднується від route і повертається в `Очікує`.

### 7.2 Маршрути

Структура:

- `route-generator` (побудова),
- `routes` (збережені маршрути і робота з курʼєрами).

Флоу:

1. `GET/POST /route-generator` або JSON optimize endpoint до external optimizer.
2. `POST /route-generator/save`:
   - створює/оновлює `DeliveryRoute`;
   - записує `RouteDelivery` стопи;
   - статус доставок переводить `Очікує -> Розподілено`.
3. `POST /routes/<id>/assign` або `/assign-and-send`:
   - призначення курʼєра;
   - за `assign-and-send` відправка в Telegram.
4. `POST /routes/<id>/delete`:
   - видалення маршруту;
   - повʼязані доставки повертаються в `Очікує`.

### 7.3 Сторінка флориста (`/florist`)

Показує доставки за обрану дату (default today), розділено на:

- route/unrouted,
- nova_poshta,
- pickup.

Bulk статуси флориста:

- `POST /florist/deliveries/status` з `status_key`:
  - `assembled` -> `Зібрано`
  - `handoff` -> `Передано кур'єру` (+ delivery.status = `Розподілено`)
  - `delivered` -> `Доставлено` (+ `delivered_at`).

Для підписок рахується індекс доставки в циклі (1..4) по order.

## 8) Dashboard follow-up

`/dashboard` рахує:

- доставки сьогодні, delivered/in-courier/unassigned;
- порівняння з аналогічним днем минулого тижня;
- new orders / new subscriptions / extended today;
- список завершених підписок для follow-up.

Follow-up дії:

- `POST /dashboard/subscriptions/<id>/status`
  - `extended` або `declined`.
- Якщо натиснуто `extended` в UI, відкривається composer extension modal замість простого POST.

## 9) Звіти (`/reports`)

Готується через `reports_service.get_reports_data(month)`:

- “Звідки дізнались” (all-time + місяць);
- “Хто кому купує” (all-time + місяць);
- розподіл типів підписок;
- розподіл розмірів;
- помісячний тренд orders/subscriptions (line chart dataset).

Нормалізація “Не вказано” робиться сервісно (merge синонімів порожніх значень).

## 10) Сертифікати

`/certificates`:

- типи: `amount`, `size`, `subscription`;
- коди: `Рxxxx` для amount/size, `Пxxxx` для subscription;
- `validate` перевіряє існування/used/expiry;
- при успішному застосуванні в `POST /orders/new` сертифікат переходить в `used`, з `order_id`.

## 11) Endpoint map (операційний мінімум)

- Auth: `/auth/login`, `/auth/logout`
- Clients: `/clients`, `/clients/new`, `/clients/<id>`, `/clients/<id>/delete`, `/clients/json`
- Orders: `/orders`, `/orders/new`, `/orders/<id>/edit`, `/orders/<id>/delete`, `/orders/deliveries/time`
- Subscriptions: `/subscriptions`, `/subscriptions/<id>`
- Extension/form helper: `/orders/extend-form-from-delivery/<delivery_id>`
- Routes generation: `/route-generator`, `/route-generator/deliveries`, `/route-generator/save`, `/route-generator/recalculate`
- Saved routes: `/routes`, `/routes/<id>/assign`, `/routes/<id>/assign-and-send`, `/routes/<id>/delete`
- Florist: `/florist`, `/florist/deliveries/status`
- Dashboard: `/dashboard`, `/dashboard/subscriptions/<id>/status`
- Reports: `/reports`
- Settings: `/settings` + довідники `/settings/*`
- Certificates: `/certificates`, `/certificates/create`, `/certificates/validate`

## 12) Важливі правила даних (інваріанти)

- Підписка завжди генерує 4 `Delivery`.
- Разове замовлення генерує 1 `Delivery`.
- У підписці час задається тільки на першу доставку.
- `is_subscription_extended=True` означає, що цикл уже позначений як продовжений.
- Доставки зі статусами `Доставлено/Скасовано` не синхроняться при edit order.

## 13) Технічні нюанси (щоб врахувати в roadmap)

- Унікальність `client.instagram/telegram/phone` зараз enforce на service-рівні, не на DB constraint.
- `get_or_create_client()` у `order_service` робить exact search по `instagram` (без додаткової нормалізації).
- Частина endpoint-ів покладається на глобальний `before_request` замість локального `@login_required/@permission_required`.

## 14) Швидкий приклад: створення акаунта флориста

```python
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    user = User(
        email='florist@kvitkova.local',
        username='florist',
        user_type='florist',
        is_active=True,
    )
    user.set_password('change_me')
    db.session.add(user)
    db.session.commit()
```

Після логіну такий користувач буде редіректитись тільки на `/florist`.
