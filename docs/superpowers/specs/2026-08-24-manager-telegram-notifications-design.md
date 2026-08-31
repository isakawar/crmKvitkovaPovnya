# Telegram-нотифікації менеджерам про нові заявки з сайту (design spec)

**Дата:** 2026-08-24
**Гілка:** `feat/wix-integration` (продовження Wix-інтеграції)

## Мета

Коли на сайті з'являється нова заявка (`WixLead`), усі CRM-користувачі з роллю
admin/manager, що прив'язали Telegram, отримують повідомлення з кнопкою
"Перейти до замовлення", яка веде напряму на передзаповнену форму
`/orders/new?lead_id=N`. Коли будь-хто (через CRM, необов'язково через того ж
менеджера) обробляє заявку, кнопка в усіх надісланих повідомленнях
автоматично змінюється на "✅ Оброблено — переглянути замовлення" і веде вже
на створене замовлення.

## Контекст (з дослідження існуючого коду)

- Telegram-прив'язка сьогодні існує лише для `Courier` (`app/models/courier.py`):
  `telegram_chat_id`, `telegram_username`, `telegram_registered`,
  `telegram_notifications_enabled`, `last_telegram_activity`. У `User`
  (`app/models/user.py`) немає жодного Telegram-поля і немає `phone`.
- Реєстрація кур'єра — два шляхи в `app/telegram_bot/handlers.py`:
  `/register <телефон>` (`register_command`, рядки 95-206) і кнопка "поділитись
  контактом" (`handle_contact`, рядки 208-278). Обидва: нормалізують телефон
  через `app.services.csv_import_service.normalize_phone`, шукають
  `Courier.query.filter_by(phone=phone)`, перевіряють `active` і що
  `telegram_chat_id` не зайнятий іншим чатом, після чого проставляють поля.
- Найближчий існуючий аналог "надіслати повідомлення з кнопкою → клік змінює
  стан → повідомлення редагується" — потік прийняття маршруту кур'єром
  (`app/blueprints/routes/routes.py`, `assign_and_send_route` +
  `_handle_route_response` у `handlers.py:1137-1275`): надсилає inline-кнопки,
  зберігає `telegram_message_id`, після відповіді кур'єра викликає
  `query.edit_message_text(...)` з новою клавіатурою.
- `TelegramBot` (`app/telegram_bot/bot.py`) дає async API:
  `send_message(chat_id, text, reply_markup=None) -> Optional[int]` (рядок 76,
  повертає `message_id`) і
  `edit_message(chat_id, message_id, text, reply_markup=None) -> bool`
  (рядок 104). `TelegramNotificationService`
  (`app/telegram_bot/notification_service.py`) показує канонічний спосіб
  викликати ці async-методи з синхронного Flask-коду через новий event loop.
- `User` вже має `ROLE_ADMIN`/`ROLE_MANAGER` і `has_role()`/`has_permission()`
  (`app/models/user.py`), тобто ролі admin/manager вже існують — не потрібно
  створювати нову роль, лише додати Telegram-поля.
- Керування користувачами: `/settings/users` (`app/templates/settings/users.html`,
  route `settings.users_page` в `app/blueprints/settings/routes.py:41-44`),
  create/update/toggle через `/settings/users` (POST/PUT) і
  `/settings/users/<id>/toggle-active`.
- Поточний head міграцій на цій гілці: `add_wix_integration_tables`.

## Модель даних

### Зміни в `User` (`app/models/user.py`)

Нові колонки (мігрують через нову ревізію, `down_revision =
'add_wix_integration_tables'`):

| Поле | Тип | Опис |
|------|-----|------|
| `phone` | String(32), nullable, unique | Телефон для прив'язки Telegram (за зразком `Courier.phone`) |
| `telegram_chat_id` | BigInteger, nullable, unique | Chat ID в Telegram |
| `telegram_username` | String(64), nullable | |
| `telegram_registered` | Boolean, default False | |
| `telegram_notifications_enabled` | Boolean, default True | Вимкнути сповіщення, не відв'язуючи Telegram |
| `last_telegram_activity` | DateTime, nullable | |

### Нова таблиця `wix_lead_notification`

| Поле | Тип | Опис |
|------|-----|------|
| `id` | PK | |
| `wix_lead_id` | FK → wix_lead.id, indexed | |
| `user_id` | FK → user.id | Кому надіслано |
| `telegram_chat_id` | BigInteger | Дубльовано з User на момент відправки — для редагування навіть якщо User згодом відв'яже Telegram |
| `telegram_message_id` | Integer | Потрібен для `edit_message` |
| `sent_at` | DateTime | |

Одна заявка → кілька рядків (по одному на кожного менеджера, якому надіслано).

## Реєстрація менеджера в боті

Розширюємо існуючі `register_command` і `handle_contact` в
`app/telegram_bot/handlers.py`, а не додаємо нові команди — однаковий UX
для кур'єрів і менеджерів:

1. Як і зараз — спершу шукаємо `Courier.query.filter_by(phone=phone)`.
2. Якщо кур'єра не знайдено — шукаємо
   `User.query.filter_by(phone=phone).first()`, додатково перевіряючи, що
   `user.user_type in ('admin', 'manager')` або `user.has_role('admin')`/`user.has_role('manager')`.
3. Якщо знайдено — та сама логіка: перевірка `is_active`, перевірка що
   `telegram_chat_id` не зайнятий іншим чатом, потім проставляємо
   `telegram_chat_id`, `telegram_username`, `telegram_registered=True`,
   `last_telegram_activity`.
4. Якщо не знайдено ні кур'єра, ні відповідного User — те саме повідомлення
   про помилку, що й зараз ("зверніться до адміністратора").

У `/settings/users` (`users.html` + `routes.py`) додається:
- Індикатор статусу Telegram для admin/manager-рядків у таблиці (як зараз
  показано в `couriers.html`).
- Кнопка "Скинути Telegram" → `POST /settings/users/<id>/reset-telegram`
  (новий route, обнуляє ті самі 5 полів, за зразком
  `app/blueprints/couriers/routes.py` `reset_courier_telegram`).

Ручного створення "менеджера для нотифікацій" через окрему форму не буде —
адмін просто відкриває вже існуючого admin/manager User і бачить, чи
прив'язаний Telegram.

## Сервіс: `app/telegram_bot/manager_notification_service.py`

Нова функція `send_new_lead_notification(lead: WixLead) -> None`:

1. Перевіряє `current_app.telegram_bot.is_initialized()` — якщо ні, лог
   warning і вихід (бот не сконфігурований, як у `TelegramNotificationService`).
2. `recipients = User.query.filter(
   User.telegram_chat_id.isnot(None),
   User.telegram_notifications_enabled.is_(True),
   User.user_type.in_(('admin', 'manager'))
   ).all()`
3. Формує текст:
   ```
   🆕 Нова заявка з сайту #{wix_order_number}

   {contact_name}
   {contact_phone}

   {item_name}
   {amount} {currency}
   ```
4. Клавіатура — одна URL-кнопка:
   `[{'text': '🛒 Перейти до замовлення', 'url': f'{CRM_PUBLIC_URL}/orders/new?lead_id={lead.id}'}]`
5. Для кожного отримувача: викликає `send_message` через той самий
   event-loop-bridge патерн, що й `TelegramNotificationService`; отриманий
   `message_id` зберігає в новий рядок `WixLeadNotification`.
6. Помилка надсилання одному отримувачу (заблокував бота, чат видалено) —
   логується і пропускається, не перериває розсилку іншим.

### Виклик з webhook-роуту

`app/blueprints/integrations/routes.py`, у `wix_order_webhook`: перед
викликом `create_or_update_lead` перевіряємо, чи лід із таким
`wix_order_id` уже існує (`existing_before = WixLead.query.filter_by(
wix_order_id=parsed['wix_order_id']).first()`). Якщо `existing_before is
None` — після успішного створення виклик
`send_new_lead_notification(lead)`. Це гарантує, що повторна доставка
вебхука від Wix (ідемпотентність, вже реалізована в `create_or_update_lead`)
не спамить менеджерів дублями.

### Редагування повідомлень при обробці

У `app/services/wix_integration_service.py`, `mark_lead_processed(lead,
entity, user)` — після існуючого `db.session.commit()` додається виклик
нової `notify_lead_processed(lead)` (у тому ж `manager_notification_service.py`):

1. `WixLeadNotification.query.filter_by(wix_lead_id=lead.id).all()`.
2. Визначає URL реального замовлення:
   - `Order` → `/orders/{lead.processed_order_id}/edit`
   - `Subscription` (лід не має власного `processed_order_id`, окрім
     першого замовлення підписки, яке вже зберігається в
     `processed_order_id`) → та сама логіка, `/orders/{lead.processed_order_id}/edit`,
     якщо є; інакше просто `/orders` (edge case: підписка без жодного
     замовлення ще не створеного — малоймовірно, оскільки перший цикл
     генерується одразу).
3. Для кожного `WixLeadNotification` викликає `edit_message` з новим
   текстом (додає рядок `✅ Оброблено {user.display_name or user.username},
   {час}`) і новою клавіатурою — одна кнопка
   `[{'text': '✅ Оброблено — переглянути замовлення', 'url': ...}]`.
4. Помилка редагування одного повідомлення (видалене повідомлення, чат
   заблокував бота, повідомлення старіше 48 год — Telegram API обмеження)
   логується і пропускається, не блокує створення замовлення.

## Конфігурація

Новий env `CRM_PUBLIC_URL` (`app/config.py`, обидва класи `Config` і
`DevelopmentConfig`, за зразком `WIX_ALLOWED_SITE_IDS`) — базовий URL для
формування посилань у Telegram-повідомленнях (localhost не буде доступний з
телефону менеджера; для реального продакшена — публічний домен CRM, для
локального тесту — той самий тимчасовий тунель, що й для Wix-вебхука).
Якщо `CRM_PUBLIC_URL` не задано — `send_new_lead_notification` логує
warning і не надсилає повідомлень (як `WIX_ALLOWED_SITE_IDS` — fail-closed,
не намагається вгадати localhost-посилання, яке однаково не спрацює).

## Помилки та edge cases

- Менеджер без прив'язаного Telegram — просто не отримує сповіщень, без
  помилки.
- Один і той самий телефон одночасно в `Courier` і в `User` (малоймовірно,
  але можливо) — реєстрація в боті пріоритетно матчить `Courier` (як і
  зараз), `User`-гілка перевіряється тільки якщо кур'єра не знайдено.
- `WIX_ALLOWED_SITE_IDS` не сконфігурований → вебхук взагалі не працює
  (503, вже реалізовано) — сповіщення тоді не актуальні.
- `CRM_PUBLIC_URL` не сконфігурований → сповіщення тихо не надсилаються
  (лог warning), заявка все одно з'являється в CRM і видима на сторінці
  "Заявки з сайту".
- Заявка оброблена, але жодного `WixLeadNotification` не було (бот не був
  сконфігурований на момент надходження заявки) — `notify_lead_processed`
  просто нічого не редагує (порожній список).

## Міграція

Нова ревізія `add_user_telegram_and_lead_notifications`, `down_revision =
'add_wix_integration_tables'`: додає 6 колонок до `user` +
створює таблицю `wix_lead_notification`.

## Тестування

- Реєстрація менеджера через `/register <телефон>` і через `handle_contact`:
  успішний кейс, кейс "телефон не знайдено ні в Courier, ні в підходящому
  User", кейс "вже прив'язано до іншого чату", кейс "User знайдений, але
  роль не admin/manager" (не реєструється).
- `send_new_lead_notification`: розсилає всім admin/manager з прив'язаним
  Telegram і `telegram_notifications_enabled=True`; не надсилає тим, у кого
  немає `telegram_chat_id` або нотифікації вимкнені; зберігає
  `WixLeadNotification` для кожного успішного надсилання; не падає, якщo
  бот не ініціалізований або `CRM_PUBLIC_URL` не заданий.
- Ідемпотентність: повторний webhook-виклик з тим самим `wix_order_id` НЕ
  викликає `send_new_lead_notification` вдруге.
- `notify_lead_processed`: редагує всі надіслані повідомлення для ліда;
  кнопка веде на `/orders/{processed_order_id}/edit`; не падає, якщо
  `WixLeadNotification` для ліда немає.
- `/settings/users` reset-telegram: обнуляє всі 5 полів, як
  `reset_courier_telegram` для кур'єрів.

## Поза скоупом (MVP)

- Двонаправлена синхронізація (менеджер щось міняє в боті — назад у CRM,
  окрім самого факту реєстрації).
- Призначення заявки конкретному менеджеру / черга "хто перший забрав".
- Push-нотифікації для florist-ролі чи інших user_type — тільки
  admin/manager.
- Redis/async-черга для розсилки — надсилання відбувається синхронно
  всередині webhook-запиту (кілька HTTP-викликів до Telegram API за один
  вебхук; прийнятно для очікуваного обсягу заявок з одного магазину).
