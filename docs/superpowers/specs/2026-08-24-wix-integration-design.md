# Wix → CRM інтеграція (design spec)

**Дата:** 2026-08-24
**Гілка:** `feat/wix-integration`

## Мета

Замовлення, оформлені клієнтом на сайті (Wix), автоматично потрапляють у CRM як
"заявка з сайту" (лід). Адмін/менеджер відкриває заявку, максимум полів вже
передзаповнено (клієнт, отримувач, адреса, розмір, тип — разове/підписка), і
одним кліком перетворює її на `Order` або `Subscription` через існуючу форму
`/orders/new`. Повна автоматизація (без участі людини) — не мета: людина завжди
підтверджує/редагує перед створенням.

## Вхідні дані

Wix Automation (тригер `wix_e_commerce-order_placed`) шле POST з JSON-об'єктом
у формі `order` Wix eCommerce API — приклад повного payload зафіксовано в задачі
(`orderNumber`, `contact.{name,email,phones[]}`, `shippingInfo.logistics.shippingDestination.address`,
`lineItems[].{catalogItemId,itemName,quantity,totalPrice}`, `id` — унікальний Wix order id).

Проміжний debug-relay (`lhr.life`), що фігурує у прикладі — тимчасовий тунель
для відлагодження зі сторони власника сайту і не є частиною продової архітектури.
CRM приймає POST напряму від Wix Automations.

## Архітектура

### Нові таблиці

**`wix_lead`**
| Поле | Тип | Опис |
|------|-----|------|
| `id` | PK | |
| `wix_order_id` | String, unique, indexed | `data.id` з Wix payload — ключ ідемпотентності |
| `wix_order_number` | String | `data.orderNumber`, для відображення |
| `raw_payload` | JSON | повний вхідний payload, для аудиту/діагностики |
| `status` | String | `new` \| `processed` \| `ignored` |
| `received_at` | DateTime | час отримання webhook |
| `contact_name` | String | розпарсене ім'я + прізвище отримувача/контакту |
| `contact_phone` | String | нормалізований `+380...` (перший телефон) |
| `contact_email` | String | |
| `city` / `street` / `postal_code` / `address_comment` | String | з `shippingInfo` (fallback на `contact.address`) |
| `item_name` | String | назва першої позиції `lineItems` |
| `catalog_item_id` | String | для мапінгу |
| `quantity` | Integer | |
| `amount` | Numeric | `priceSummary.total.value` |
| `currency` | String | |
| `payment_status` | String | `data.paymentStatus` |
| `matched_client_id` | FK → client, nullable | результат автоматичного матчингу |
| `mapping_matched` | Boolean | чи знайдено `WixProductMapping` для `catalog_item_id` |
| `processed_order_id` | FK → order, nullable | |
| `processed_subscription_id` | FK → subscription, nullable | |
| `processed_at` | DateTime, nullable | |
| `processed_by_user_id` | FK → user, nullable | |

Множинні `lineItems` в MVP не підтримуються як кілька замовлень — беремо перший
item для префілу; якщо їх декілька, лід все одно створюється (з повним
`raw_payload`), але в списку позначається "кілька позицій — перевірте вручну".

**`wix_product_mapping`**
| Поле | Тип | Опис |
|------|-----|------|
| `id` | PK | |
| `catalog_item_id` | String, unique, indexed | `lineItems[].catalogItemId` з Wix |
| `wix_item_name` | String | остання відома назва товару (довідково, оновлюється при новому ліді з тим самим ID) |
| `order_scenario` | String | `order` \| `subscription` |
| `delivery_type` | String, nullable | для `subscription`: `Weekly`/`Monthly`/`Bi-weekly` |
| `size` | String | `S`/`M`/`L`/`XL`/`XXL` |
| `for_whom` | String, nullable | дефолтне значення, менеджер може змінити при обробці |
| `is_active` | Boolean, default true | |

Керується вручну адміном через CRUD-сторінку. Немапований `catalog_item_id` не
блокує створення ліда — просто `mapping_matched=False`, і на сторінці обробки
розмір/тип потрібно вибрати вручну (як зараз для звичайного замовлення).

### Сервіс: `app/services/wix_integration_service.py`

- `parse_wix_payload(payload: dict) -> dict` — витягує всі поля вище з сирого
  Wix JSON (контакт, адреса, перший line item, суми).
- `normalize_phone` — перевикористовується з `app/services/csv_import_service.py`
  (вже є нормалізація UA-номерів до `+380...`).
- `find_matching_client(parsed: dict) -> Client | None` — пошук `Client` спершу
  за `phone == contact_phone`, якщо не знайдено — за `email == contact_email`.
- `find_product_mapping(catalog_item_id: str) -> WixProductMapping | None`.
- `create_or_update_lead(payload: dict) -> WixLead` — ідемпотентно: якщо
  `wix_order_id` вже існує, оновлює `raw_payload`/розпарсені поля лише якщо
  статус ще `new` (не чіпає вже оброблені/ігноровані), інакше повертає існуючий
  запис без змін. Викликає парсинг + матчинг клієнта + мапінг товару.

### Блюпринт: `app/blueprints/integrations/`

- `POST /api/integrations/wix/order-placed` — публічний вебхук.
  - Авторизація: query-параметр `?token=...` (або заголовок `X-Webhook-Token`),
    звіряється через `hmac.compare_digest` з env `WIX_WEBHOOK_SECRET`. Немає
    токена / не збігається → `401`.
  - Тіло розбирається як JSON (`request.get_json(silent=True)`); порожнє/невалідне
    тіло → `400`, лід не створюється.
  - На валідний токен + JSON — завжди `200 {"ok": true, "lead_id": ...}`, навіть
    якщо парсинг часткового не вдався (сирий payload все одно зберігається,
    помилки логуються) — щоб Wix не ретраїв і жодні дані не губились.
  - `@csrf` не потрібен — у проєкті немає глобального Flask-WTF CSRF.
- `GET /integrations/wix-leads` — список лідів (admin/manager, `@login_required`
  + перевірка ролі як в інших блюпринтах), фільтр за статусом (`new` за
  замовчуванням), сортування за `received_at desc`. Показує: бейдж статусу,
  товар, суму, контакт, чи знайдено клієнта/мапінг.
  - Кнопка "Обробити" → `/orders/new?lead_id=<id>`.
  - Кнопка "Ігнорувати" → `POST /integrations/wix-leads/<id>/ignore`.
- `GET /integrations/wix-product-mappings`, `POST .../new`, `POST .../<id>/edit`,
  `POST .../<id>/delete` — проста CRUD-адмінка для `WixProductMapping`.
- Пункт меню верхнього рівня "Інтеграції" з двома вкладками: "Заявки з сайту" і
  "Мапінг товарів".

### Префіл форми замовлення

`GET /orders/new` (`app/blueprints/orders/routes.py:order_form`) додатково
приймає `?lead_id=<id>`. Якщо лід існує і `status == 'new'`, у контекст шаблону
додається `wix_lead` (dict з готовими значеннями для форми: client або
client_search_query, recipient_name/phone, city/street/address_comment,
delivery_method='courier', size, order_scenario/delivery_type, for_whom,
comment з посиланням на номер замовлення Wix і суму). Шаблон
`orders/form.html` рендерить приховане поле `lead_id` і, де можливо,
`value="{{ wix_lead.recipient_name }}"` тощо (звірка з існуючими name-атрибутами
полів форми — без переписування композер-скрипта, тільки додавання
value/selected на основі `wix_lead`).

`POST /orders/new` (`order_create`) — якщо в форм-даних є `lead_id`, після
успішного створення `Order`/`Subscription` викликає
`wix_integration_service.mark_lead_processed(lead, entity, current_user)`, що
виставляє `status='processed'`, `processed_order_id`/`processed_subscription_id`,
`processed_by_user_id`, `processed_at`.

## Помилки та edge cases

- Дубльований webhook (Wix retry) з тим самим `wix_order_id` → без дублювання
  ліда (upsert по unique constraint).
- Немапований товар → лід створюється, форма префілиться без розміру/типу,
  менеджер заповнює вручну.
- Клієнт не знайдений → лід створюється без `matched_client_id`; на сторінці
  `/orders/new?lead_id=...` поле клієнта не передзаповнюється, менеджер обирає
  існуючого або створює нового через Instagram (як зараз) — CRM Client матчиться
  окремо, без автостворення на етапі webhook.
- Заявка вже `processed`/`ignored`, а до неї повертаються по прямому URL
  `?lead_id=` — форма показує попередження "заявку вже оброблено" і не префілить.
- `WIX_WEBHOOK_SECRET` не заданий в env → ендпоінт відповідає `503` (інтеграція
  не сконфігурована), щоб не тримати публічний ендпоінт відкритим за замовчуванням.

## Міграція

Дві нові таблиці (`wix_lead`, `wix_product_mapping`). Перед створенням файлу
міграції — знайти актуальний head за правилом з `CLAUDE.md` (`grep -r
"down_revision" migrations/versions/*.py`).

## Тестування

- `parse_wix_payload` на прикладі реального payload із задачі → очікувані
  розпарсені поля.
- Ідемпотентність: два виклики `create_or_update_lead` з однаковим
  `wix_order_id` → один запис `WixLead`.
- Матчинг клієнта: existing client за телефоном/email знаходиться; відсутність
  збігу → `matched_client_id is None`.
- Webhook auth: запит без токена / з неправильним токеном → `401`; без
  `WIX_WEBHOOK_SECRET` в конфігу → `503`.
- `order_form` з `?lead_id=` префілить контекст очікуваними значеннями;
  повторний виклик після `processed` не префілить.
- `order_create` з `lead_id` у формі переводить лід у `processed` і зв'язує з
  правильним `Order`/`Subscription`.
- CRUD `WixProductMapping`: створення/редагування/видалення мапінгу впливає на
  `mapping_matched` наступного ліда з тим самим `catalog_item_id`.

## Поза скоупом (MVP)

- Обробка кількох `lineItems` як кількох замовлень одночасно.
- Синхронізація статусу оплати/повернень з Wix після створення ліда.
- Автоматичне створення `Order`/`Subscription` без участі людини.
- Двосторонній зв'язок (CRM → Wix) — оновлення статусу замовлення на сайті.
