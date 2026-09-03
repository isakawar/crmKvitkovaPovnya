# Омниканальный инбокс (чат) — этап 1: Telegram Business

## Статус
in_progress — v1 backend+frontend готовы, тесты зелёные (369+17 passed);
миграция не применена (ждёт commit), E2E с реальным ботом не проводился.

## Задача
Единый чат в CRM, куда стягиваются диалоги с корпоративных аккаунтов (Telegram → потом
Instagram, Viber, WhatsApp). Менеджеры с выданным доступом отвечают клиентам прямо из CRM.
Этап 1 — только Telegram через Business API (личный номер с Premium + бизнес-режим).

Полный план: `~/.claude/plans/wise-greeting-matsumoto.md`.

## План
- [ ] Модели: `MessagingChannel`, `MessagingChannelAccess`, `Conversation`, `Message`
- [ ] Конфиг: `INBOX_TELEGRAM_BOT_TOKEN`, `INBOX_MEDIA_*`
- [ ] `app/services/messaging/`: adapter (Protocol), telegram_business, inbox_service, channel_config_service
- [ ] Blueprint `inbox`: страница, JSON-поллинг, reply, read/assign/close, media, webhook
- [ ] Регистрация в `app/__init__.py`: bp, public_endpoints, context processor, CLI
- [ ] Настройка канала: `/settings/messaging` + шаблон
- [ ] Навбар: значок непрочитанного + пункт меню
- [ ] Фронтенд: `inbox/index.html` + `inbox.js` (setTimeout-поллинг)
- [ ] Alembic-миграция (найти head!)
- [ ] Тесты: adapter.parse_events, inbox_service, webhook-роут

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

## Этап 2 — Instagram (реализован, commit 2)

- `app/services/messaging/instagram_dm.py` — `InstagramDMAdapter` (Instagram API with Instagram
  Login, `graph.instagram.com`, без FB Page). `verify_subscription` (GET hub.challenge vs
  `channel.webhook_secret`), `verify_webhook` (X-Hub-Signature-256 c `INBOX_INSTAGRAM_APP_SECRET`),
  `parse_events` (пропуск echo/deleted), `download_media` (по CDN-URL из attachment),
  `enrich_contact` (name/username по IGSID), `send_text`. `send_media` → пока ошибка (нужен public URL).
- Роут `GET|POST /api/messaging/instagram/<channel_id>/webhook`, общий хендлер `_handle_webhook`.
  `telegram_webhook`/`instagram_webhook` проверяют `channel.channel_type`.
- `adapter.ChannelAdapter`: `verify_webhook(request, channel)` (был `headers`), новый `verify_subscription`.
- `inbox_service.ingest_event` — узнаёт `channel.external_id` (IG account id) из первого вебхука;
  `_get_or_create_conversation` вызывает `enrich_contact` для новых диалогов.
- Config: `INBOX_INSTAGRAM_ACCESS_TOKEN`, `INBOX_INSTAGRAM_APP_SECRET`, `INBOX_INSTAGRAM_GRAPH_VERSION`.
- `/settings/messaging` — выбор типа канала при создании, показ Webhook URL + Verify token,
  подсказка про Meta App Dashboard. CLI `flask messaging-refresh-instagram <id>`.
- Тесты: `test_messaging_instagram_adapter.py` (7) + 3 в inbox_service. Всего 379+27 passed.

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

## Осталось / следующие шаги
- Применить миграцию: `git commit` → `flask db upgrade` (правило проекта).
- E2E Telegram: BotFather → .env → /settings/messaging → Telegram Business → Chatbots.
- E2E Instagram: создать Meta App (Instagram API w/ Instagram Login), App Review для
  `instagram_business_manage_messages`, вставить Webhook URL+Verify token в Meta Dashboard,
  подписаться на `messages`, получить long-lived token в `.env`.
- Instagram: исходящие фото (нужен публичный URL для медиа); 24-часовое окно ответа.
- Viber / WhatsApp адаптеры.
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
