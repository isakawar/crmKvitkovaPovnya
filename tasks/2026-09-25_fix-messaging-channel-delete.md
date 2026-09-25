# Видалення каналу інбоксу не працює

## Статус
done

## Задача
Кнопка «Видалити» в `/settings/messaging` нічого не робила для каналу з діалогами.
Потрібно, щоб канал видалявся разом з усіма діалогами, повідомленнями і медіа —
щоб на тесті відключити тестовий акаунт і підключити продовий.

Причина: `MessagingChannel.conversations` без cascade → SQLAlchemy перед DELETE
робив `UPDATE messaging_conversation SET channel_id = NULL` → NOT NULL violation → 500.
JS не обробляв помилку (`r.json()` на HTML-сторінці 500 кидав виняток), тому тиша.

## План
- [x] Модель: `passive_deletes=True` на `conversations`
- [x] `channel_config_service.delete_channel`: явно видаляє повідомлення, діалоги, медіафайли з диска
- [x] JS: `api()` не падає на не-JSON відповіді; тост з помилкою при невдалому видаленні
- [x] Тест

## Реалізація
- `app/models/messaging_channel.py` — `passive_deletes=True`, ORM більше не занулює `channel_id`.
- `app/services/messaging/channel_config_service.py` — `delete_channel` видаляє файли медіа
  (`INBOX_MEDIA_FOLDER`), знімає self-FK `reply_to_message_id`, bulk-delete повідомлень і
  діалогів, потім канал. Не покладається на `ON DELETE CASCADE` (SQLite в тестах FK не enforce-ить).
- `app/templates/settings/messaging.html` — `api()` повертає `{success:false, error}` на не-JSON;
  тост при помилці видалення.
- `tests/unit/test_messaging_inbox_service.py` — `test_delete_channel_removes_conversations_messages_and_media`.

## Як тестувати
1. `/settings/messaging` → «Видалити» на каналі з діалогами → confirm.
2. Сторінка перезавантажується, каналу немає; в `/inbox` його діалогів немає.
3. Для `telegram_personal` — після видалення `docker compose restart telegram-personal-bot`.
4. Підключити новий акаунт як звичайно.

## Edge cases
- Діалоги інших каналів не зачіпаються (покрито тестом).
- Файл медіа вже видалений (purge) — ігнорується.
- Пов'язані з діалогами клієнти CRM не видаляються (FK `client_id` лише на боці діалогу).
- Pre-existing: 2 падаючі тести `test_send_reply_*` (лямбди-заглушки без `reply_to_external_id`) — не пов'язані.
