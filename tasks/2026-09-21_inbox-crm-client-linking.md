# Прив'язка розмов інбоксу до клієнтів CRM + права панель

## Статус
done

## Задача
`Conversation.client_id` існував у схемі, але ніде не заповнювався
("не populated in v1"). Треба: (1) автоматично зв'язувати нову розмову з
існуючим клієнтом CRM за Instagram/Telegram-хендлом чи телефоном, (2) дати
менеджеру ручний спосіб прив'язати/відв'язати, (3) показати праворуч у
треді інформацію про клієнта — контакти, знижку/баланс, активну підписку,
історію доставок.

## Реалізація

### Матчинг (`app/services/client_service.py`)
- `find_client_for_contact(channel_type, username=None, phone=None)` —
  точний, неоднозначний матч. Використовує вже наявні на `Client` поля
  `instagram`/`telegram`/`phone` + прапорці `phone_viber`/`phone_telegram`/
  `phone_whatsapp` (вони вже існували в схемі саме для цього).
  - `instagram` → `Client.instagram` (регістронезалежно, з/без `@`)
  - `telegram`/`telegram_personal` → `Client.telegram`, якщо немає —
    fallback на `Client.phone` за умови `phone_telegram=True`
  - `whatsapp` → `Client.phone` за умови `phone_whatsapp=True`
  - `viber` → `Client.phone` за умови `phone_viber=True`
  - Телефон нормалізується через вже наявний
    `csv_import_service.normalize_phone` (не писав новий парсер).
  - **Рівно один збіг → прив'язка. Нуль або декілька → `None`, нічого не
    вгадуємо.**
- `_handle_match()` — приватний хелпер для регістронезалежного `@handle`
  порівняння (той самий патерн, що вже був у `_validate_contact_fields`,
  винесений в перевикористовувану форму).

### Де викликається матчинг
`inbox_service._get_or_create_conversation()` — одразу після створення
нової розмови (best-effort, обгорнуто в try/except, як і `enrich_contact`
поруч). **Не** ретроактивно пере-сканує вже існуючі розмови — якщо клієнта
додали в CRM пізніше, ніж він написав уперше, менеджер прив'язує вручну.

### Ручне прив'язати/відв'язати (`app/blueprints/inbox/routes.py`)
- `GET /inbox/conversations/<id>/client-panel` — дані для правої панелі.
- `POST /inbox/conversations/<id>/link-client {client_id}` /
  `POST .../unlink-client`.
- `GET /inbox/clients/search?q=` — тонка обгортка над вже наявним
  `client_service.search_clients()` (не писав нову пошукову логіку).

### Права панель (`get_client_panel`, `inbox_service.py`)
Повертає (якщо `conv.client_id` заповнено):
- Клієнт: ім'я, телефон, instagram/telegram, знижка, баланс, посилання
  на `/clients/<id>`.
- **Підписка**: перший `Subscription` зі `status='active'` для клієнта —
  тип, розмір, день доставки, весільна чи ні.
- **Доставки**: останні 8 напряму по `Delivery.client_id` (пряма FK,
  запит без join через Order).

### Фронтенд
- `app/templates/inbox/index.html` — `#ib-thread-body` став рядком:
  існуючий стовпець (шапка/повідомлення/composer) обгорнуто в
  `.ib-thread__main`, поруч нова `.ib-client-panel` (264px, схована на
  мобільних — той самий `@media (max-width:768px)` блок).
- `app/static/js/inbox.js`:
  - `fetchClientPanel(convId)` — викликається з `openConv()`.
  - `renderClientPanel(data)` — два стани: прив'язано (картка клієнта +
    підписка + доставки + "Відв'язати") чи ні (пошук з debounce 300мс →
    клік по результату → `link-client`).
  - Дати доставок форматуються в `dd.mm.yyyy` (було ISO — не відповідало
    стилю решти CRM, помітив і поправив під час скріншот-перевірки).

### Тести
- `tests/unit/test_client_service.py` — 7 нових на `find_client_for_contact`
  (з/без `@`, регістр, fallback телефон→прапорець каналу, нормалізація
  сирого формату телефону, відсутність збігу, неоднозначний збіг —
  не вгадує).
- `tests/unit/test_messaging_inbox_service.py` — 6 нових: авто-лінк при
  ingest (є збіг / немає збігу), link/unlink роут (+ round-trip через
  `get_client_panel`), відхилення неіснуючого `client_id`, `client-panel`
  для непов'язаної розмови, `clients/search` роут. Додано хелпер
  `_logged_in_client()` (аутентифікація через `session_transaction`,
  бо ці роути `@login_required`, а попередні тести файлу торкались лише
  публічних webhook-ендпоінтів).

## Як тестувати
`pytest tests/unit -k "messaging or inbox or client_service"` — 85
проходять. Повний набір — 436 passed, 3 xfailed (без регресій).

Візуально перевірено на локальному dev-сервері (sqlite, без Docker):
насіяв клієнта з активною підпискою (Weekly, ЧТ) і 4 доставками
(1 очікує, 3 доставлено), прив'язав до розмови — права панель показала
все коректно: контакти, 10% знижка, 350 балансу, зелений блок підписки,
список доставок у форматі dd.mm.yyyy.

## Edge cases
- Кілька клієнтів з однаковим handle (дублікат у CRM) — `find_client_for_contact`
  свідомо повертає `None`, не вгадує; покрито тестом.
- Viber-розмови зараз **не можуть** авто-матчитись — Viber-вебхук не
  віддає ні телефон, ні username контакта (тільки ім'я, яке ненадійне
  для матчингу). Прив'язка лише вручну через пошук.
- Телефон з різних адаптерів приходить у різному сирому форматі
  (`380991112233` без `+`, з ведучим `0` тощо) — покладаюсь на вже
  протестований `normalize_phone`, а не пишу новий парсинг.
- Клієнта відв'язали, потім знову написав — авто-матч спрацює знову при
  **новій** розмові, але не для вже існуючої (яку саме відв'язали) —
  свідомо, щоб не "воювати" з ручним рішенням менеджера.
