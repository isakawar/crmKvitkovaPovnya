# Омниканальный инбокс (чат) — этап 1: Telegram Business

## Статус
in_progress — Telegram (Business API + особистий номер), Viber, Instagram і WhatsApp готові й
покриті UI. Instagram підключається через Facebook Login for Business (OAuth-кнопка), WhatsApp —
через Facebook Embedded Signup (JS-попап) — обидва без ручного копіювання токенів, той самий Meta
App. Гілка `feature/messaging-service`, в `main` не влита, локально не запушена. Тести зелені
(49 passed: Telegram Business + Instagram + WhatsApp + Facebook OAuth + inbox_service) —
**Viber і Telegram-personal адаптери без тестів**.
Міграції (`add_messaging_inbox`, `add_telegram_personal_channel`, `add_instagram_facebook_oauth`,
`add_whatsapp_channel`) застосовані на локальній dev-БД (⚠ двічі підряд застосовані до коміту —
порушення правила проекту, виправити порядок цим комітом). E2E з реальними акаунтами не
проводився для жодного каналу; для Instagram і WhatsApp потрібен Meta App з продуктами Facebook
Login for Business + Embedded Signup — інструкцію для клієнта передано окремим PDF
(`FACEBOOK_APP_ID`, `INBOX_INSTAGRAM_APP_SECRET`, `FACEBOOK_WHATSAPP_CONFIG_ID` в `.env`, всі три
поки не задані).

## Задача
Единый чат в CRM, куда стягиваются диалоги с корпоративных аккаунтов (Telegram → потом
Instagram, Viber, WhatsApp). Менеджеры с выданным доступом отвечают клиентам прямо из CRM.
Этап 1 — только Telegram через Business API (личный номер с Premium + бизнес-режим).

Полный план: `~/.claude/plans/wise-greeting-matsumoto.md`.

## План
- [x] Модели: `MessagingChannel`, `MessagingChannelAccess`, `Conversation`, `Message`
- [x] Конфиг: `INBOX_TELEGRAM_BOT_TOKEN`, `INBOX_MEDIA_*`
- [x] `app/services/messaging/`: adapter (Protocol), telegram_business, inbox_service, channel_config_service
- [x] Blueprint `inbox`: страница, JSON-поллинг, reply, read/assign/close, media, webhook
- [x] Регистрация в `app/__init__.py`: bp, public_endpoints, context processor, CLI
- [x] Настройка канала: `/settings/messaging` + шаблон
- [x] Навбар: значок непрочитанного + пункт меню
- [x] Фронтенд: `inbox/index.html` + `inbox.js` (setTimeout-поллинг)
- [ ] Alembic-миграция (найти head!) — файлы созданы, **не применены**
- [~] Тесты: adapter.parse_events, inbox_service, webhook-роут — есть для Telegram Business +
  Instagram + inbox_service (29 шт); **нет для Viber и Telegram-personal**

## Реализация (v1 — backend + базовый фронт готовы)

Новые файлы:
- Модели: `app/models/messaging_channel.py`, `messaging_channel_access.py`, `conversation.py`,
  `message.py` (+ импорт в `app/models/__init__.py`). Таблицы: `messaging_channel`,
  `messaging_channel_access`, `messaging_conversation`, `messaging_message`.
- Сервис: `app/services/messaging/` — `adapter.py` (Protocol `ChannelAdapter`, `InboundEvent`,
  `SentResult`, `get_adapter`), `telegram_business.py` (`TelegramBusinessAdapter` через `requests`),
  `inbox_service.py` (доменная логика, без Flask), `channel_config_service.py` (CRUD + webhook).
- Blueprint: `app/blueprints/inbox/` — страница `/inbox`, JSON-поллинг, reply (text+file),
  read/assign/close/reopen, `/inbox/media/<msg>/<idx>` (ленивое скачивание),
  `POST /api/messaging/telegram/<channel_id>/webhook` (public, проверка secret-token).
- Шаблоны: `app/templates/inbox/index.html`, `app/templates/settings/messaging.html`;
  `app/static/js/inbox.js` (setTimeout-поллинг: список 10с, тред 5с, пауза в фоне).
- Миграция: `migrations/versions/add_messaging_inbox.py` (down_revision = `add_address_coordinates`).
- Тесты: `tests/unit/test_messaging_telegram_adapter.py`, `test_messaging_inbox_service.py` (17 шт, зелёные).

Правки:
- `app/config.py` — `INBOX_TELEGRAM_BOT_TOKEN`, `INBOX_MEDIA_FOLDER`, `INBOX_MEDIA_MAX_BYTES`.
- `app/__init__.py` — регистрация bp, `inbox.telegram_webhook` в `public_endpoints`,
  context processor `inject_inbox_unread`, CLI `flask messaging-set-webhook <id>`, mkdir media.
- `app/blueprints/settings/routes.py` — `/settings/messaging` + CRUD каналов/доступа/webhook.
- `app/templates/layout.html` — пункт меню «Чат / Інбокс» + значок непрочитанного (обе панели).
- `app/templates/settings/index.html` — карточка «Чат / Інбокс».
- `env.example`, `npm run build`.

## Этап 2 — Instagram (реализован, commit 2; переписан в этапе 6 под OAuth)

- `app/services/messaging/instagram_dm.py` — `InstagramDMAdapter`. `verify_subscription` (GET
  hub.challenge vs `channel.webhook_secret`), `verify_webhook` (X-Hub-Signature-256 c
  `INBOX_INSTAGRAM_APP_SECRET`), `parse_events` (пропуск echo/deleted), `download_media` (по
  CDN-URL из attachment), `enrich_contact` (name/username по IGSID), `send_text`. `send_media` →
  пока ошибка (нужен public URL).
- Роут `GET|POST /api/messaging/instagram/<channel_id>/webhook`, общий хендлер `_handle_webhook`.
  `telegram_webhook`/`instagram_webhook` проверяют `channel.channel_type`.
- `adapter.ChannelAdapter`: `verify_webhook(request, channel)` (был `headers`), новый `verify_subscription`.
- `inbox_service.ingest_event` — узнаёт `channel.external_id` (IG account id) из первого вебхука;
  `_get_or_create_conversation` вызывает `enrich_contact` для новых диалогов.
- ⚠ Изначально (`graph.instagram.com`, Instagram API with Instagram Login, глобальный env-токен)
  — этот подход **заменён** этапом 6 на Facebook Login OAuth, см. ниже.

## Этап 3 — UI (коммиты `9388510`, `0b90853`)

`inbox/index.html` + `inbox.js` переписаны под дизайн CRM (stone/amber):
- список: аватар с инициалами + бейдж канала, относительное время, жирный на непрочитанных +
  счётчик, чип назначенного менеджера, активный акцент, поиск по имени, табы Активні/Закриті
- тред: шапка с контактом (аватар, канал, @username, назначенный), разделители по датам,
  бабблы in/out с галочками доставки и текстом ошибки, миниатюры фото + lightbox по клику
- композер: авто-рост textarea, Enter=отправить / Shift+Enter=перенос, вложение фото с чипом-превью
- шапка: чипы подключённых каналов, тумблер звука (localStorage + WebAudio beep на новое)
- мобильно: переключение список↔тред с кнопкой «назад»; poll до 30с когда вкладка скрыта
- закрытые диалоги переоткрываются из треда; назначение сразу видно в шапке

## Этап 4 — Telegram «особистий номер» / MTProto (реализован, за рамками исходного плана)

- `app/services/messaging/telegram_personal.py` — адаптер `TelegramPersonalAdapter`
  (`channel_type='telegram_personal'`), без HTTP-вебхука.
- `telegram_personal_auth.py` — логин через Telethon (номер + код + 2FA), сохраняет session string.
- `session_crypto.py` — Fernet-шифрование session string в БД (`MESSAGING_SESSION_KEY`); это не
  токен бота, а bearer-эквивалент полного доступа к личному аккаунту.
- `scripts/run_telegram_personal_worker.py` — отдельный постоянный процесс (не Flask worker),
  один Telethon-клиент на канал, общий asyncio-loop, пушит входящие прямо в
  `inbox_service.ingest_event` внутри app-контекста. Нужно поднимать отдельно (systemd/supervisor
  в проде), в дев-режиме — вручную.
- `telegram_personal_backfill.py` — импорт истории переписки задним числом, CLI
  `flask messaging-backfill-telegram-personal <id> [--days]`, безопасно перезапускать.
- Фикс `48c3a69`: воркер должен пересканировать каналы периодически, а не только при старте.
- Тестов нет.

## Этап 5 — Viber (реализован, за рамками исходного плана)

- `app/services/messaging/viber.py` — `ViberAdapter` (`channel_type='viber'`), Viber Bot API,
  токен `INBOX_VIBER_BOT_TOKEN`.
- Вебхук `POST /api/messaging/viber/<channel_id>/webhook`, регистрируется через общий
  `flask messaging-set-webhook <id>` (как и Telegram).
- `/settings/messaging` — выбор канала, чип типа сообщения в списке диалогов.
- Тестов нет.

## Этап 6 — Instagram через Facebook Login for Business (OAuth, реализован)

Замена ручного Meta Dashboard-флоу на «Continue with Facebook» — по образцу KeyCRM. Полностью
заменяет способ подключения из этапа 2 (Instagram API with Instagram Login), не добавляется
параллельно.

- `app/services/messaging/facebook_oauth.py` (новый) — `authorize_url(state)`,
  `exchange_code_for_user_token`, `exchange_long_lived_token`, `list_connected_pages` (через
  `/me/accounts?fields=...instagram_business_account{id,username}`, пропускает страницы без IG).
- Модель `MessagingChannel`: новые поля `fb_page_id`, `fb_page_access_token_encrypted`
  (Fernet, тот же `session_crypto.py`, что и у `telegram_personal`).
- Миграция `add_instagram_facebook_oauth.py` (`down_revision = add_telegram_personal_channel`).
- `instagram_dm.py` переписан: `graph.facebook.com` вместо `graph.instagram.com`, токен теперь
  берётся из канала (`_page_token`), а не из глобального env. `register_webhook()` больше не
  no-op — реальный `POST /{page_id}/subscribed_apps?subscribed_fields=messages`.
- `channel_config_service.create_instagram_channel_from_page(...)` — создаёт канал сразу с
  `external_id`/`fb_page_id`/токеном из пикера, имя `Instagram (@username)`.
- Роуты (`settings/routes.py`): `GET /settings/messaging/facebook/start` (редирект на Meta OAuth,
  state в Flask-сессии для CSRF), `GET /settings/messaging/facebook/callback` (обмен кода,
  список страниц, шифрует токен перед тем как положить его в форму пикера — **не** в сессии,
  сессия у нас клиентская и не шифрована), `POST /settings/messaging/facebook/select-page`.
- Шаблон `settings/messaging_facebook_pages.html` — пикер страниц (показывает только те, где есть
  привязанный IG).
- `/settings/messaging`: кнопка «Continue with Facebook» вместо ручных полей/подсказки; в карточке
  канала — Page id + IG account id, попередження якщо канал ще не підключено.
- Config: новый `FACEBOOK_APP_ID`; `INBOX_INSTAGRAM_APP_SECRET` тепер спільний для OAuth і
  X-Hub-Signature; **`INBOX_INSTAGRAM_ACCESS_TOKEN` видалено** (більше не читається ніде).
- CLI: `messaging-refresh-instagram` замінено на `messaging-reconnect-instagram <id>` (Page-токен
  з long-lived user-токена не протухає як старий IG-токен, `refresh_token()` більше не потрібен).
- Тесты: `test_messaging_facebook_oauth.py` (6), + 4 нових в `test_messaging_instagram_adapter.py`
  (send_text/register_webhook на новому флоу). Разом 39 passed.

## Этап 7 — WhatsApp через Facebook Embedded Signup (реализован)

Той самий Meta App, що й Instagram, інший продукт (Embedded Signup) — WhatsApp-номер не
прив'язується до Facebook-сторінки, тому page-пікер не підходить, замість нього спливаюче вікно
Meta (JS SDK), яке само реєструє WhatsApp Business Account.

- `app/services/messaging/whatsapp.py` — `WhatsAppAdapter` (`channel_type='whatsapp'`). Той самий
  `graph.facebook.com`, але авторизація через `Authorization: Bearer` (не `access_token` в
  query-параметрі, як в Instagram). `parse_events` розбирає `entry[].changes[].value.messages[]`,
  пропускає `field != 'messages'` (статуси доставки), контакт (ім'я+телефон) приходить прямо у
  вебхуці — `enrich_contact` не потрібен. `download_media` — двоетапний (спочатку GET за media_id
  для тимчасового CDN URL, потім сам файл, обидва запити з Bearer-токеном — на відміну від
  Instagram, де URL публічний). `send_media` поки помилка (текст тільки, як і Instagram v1).
- `facebook_oauth.exchange_embedded_signup_code(code)` — обмін коду з попапу, **без**
  `redirect_uri` (це SDK-флоу, не URL-редірект, на відміну від Instagram-обміну).
- Роут `POST /settings/messaging/whatsapp/complete` (`settings/routes.py`) — приймає
  `{code, waba_id, phone_number_id}` з JS, обмінює код на токен, дізнається `display_phone_number`
  (окремий GET), **реєструє номер у Cloud API** (`POST /{phone_number_id}/register` з одноразовим
  PIN — обов'язковий крок перед першим використанням номера), створює канал через
  `channel_config_service.create_whatsapp_channel_from_signup`, підписує вебхук.
- Фронтенд (`messaging.html`): картка WhatsApp вантажить Facebook JS SDK
  (`connect.facebook.net/en_US/sdk.js`) лише за кліком (не одразу), `FB.login` з `config_id`
  (`FACEBOOK_WHATSAPP_CONFIG_ID`), слухає `window.addEventListener('message', ...)` від попапу
  Meta (`type: 'WA_EMBEDDED_SIGNUP'`) для `waba_id`/`phone_number_id` — код з `FB.login` і дані з
  postMessage прилітають асинхронно в довільному порядку, тому чекає обидва перед POST на бекенд.
  Якщо `FACEBOOK_APP_ID`/`FACEBOOK_WHATSAPP_CONFIG_ID` не задані — toast «ще не готове», без
  завантаження SDK.
- Модель: нові поля `wa_waba_id`, `wa_access_token_encrypted` (той самий `session_crypto.py`).
  `external_id` = `phone_number_id` (як у Instagram — IG account id).
- Міграція `add_whatsapp_channel.py` (`down_revision = add_instagram_facebook_oauth`).
- Config: новий `FACEBOOK_WHATSAPP_CONFIG_ID` (не секрет, віддається у фронтенд для JS SDK).
- Тести: `test_messaging_whatsapp_adapter.py` (10 шт). Разом з попередніми — 49 passed.
- ⚠ Точні параметри `exchange_embedded_signup_code` (відсутність `redirect_uri`) і формат
  postMessage від Meta — реалізовано за задокументованою схемою WhatsApp Cloud API, але **не
  перевірено на реальному попапі** — під час E2E майже напевно знадобляться дрібні правки.

## Осталось / следующие шаги
- Влить `feature/messaging-service` в `main` (сейчас отдельная ветка, не запушена в remote).
- ⚠ Міграції вже застосовані на локальній dev-БД **до** коміту файлів (двічі) — виправити порядок
  цим комітом (правило проекту: спочатку коміт, потім upgrade).
- Тесты для Viber и Telegram-personal адаптеров (parse_events, send_text как минимум).
- E2E Telegram (Business): BotFather → .env → /settings/messaging → Telegram Business → Chatbots.
- E2E Telegram (personal): Telethon-логин через `/settings/messaging`, поднять
  `scripts/run_telegram_personal_worker.py` как постоянный процесс.
- E2E Viber: создать бота на partners.viber.com, токен в `.env`, зарегистрировать вебхук.
- E2E Instagram (OAuth) + WhatsApp (Embedded Signup): клієнт створює Meta App за PDF-інструкцією
  (`~/Desktop/Instagram-Facebook-Setup-KvitkovaPovnya.pdf`), додає продукти Facebook Login for
  Business + WhatsApp Embedded Signup (окрема `config_id`), передає `FACEBOOK_APP_ID` +
  `INBOX_INSTAGRAM_APP_SECRET` + `FACEBOOK_WHATSAPP_CONFIG_ID`. Далі — один раз вручну прописати
  App-рівневий Webhook callback URL в Meta Dashboard для обох продуктів (API це не автоматизує),
  пройти «Continue with Facebook» / WhatsApp-картку в `/settings/messaging`.
- Instagram і WhatsApp: исходящие фото/файли (нужен публичный URL); 24-часовое окно ответа.
- WhatsApp: реальна перевірка формату postMessage і `exchange_embedded_signup_code` на живому
  попапі — найімовірніше місце для правок під час E2E.
- Опционально: SSE вместо поллинга; пинг менеджерам; связь conversation↔Client.

## Как тестувати
См. раздел «Верификация» в плане. Кратко:
1. `pytest tests/test_messaging_*.py`
2. E2E: бот от BotFather → `.env` → `/settings/messaging` → подключить вебхук →
   в Telegram Business подключить бота → написать с другого аккаунта → сообщение в `/inbox`.

## Edge cases
- Telegram retry storm → медиа не качаем в вебхуке (только file_id), ленивое скачивание.
- `BUSINESS_CONNECTION_INVALID` → message.status=failed + error + toast, канал деактивируется.
- Media groups → N отдельных сообщений (ок для v1).
- Курьерский бот (отдельный токен) не затрагивается.
