# Inbox: імена контактів і автоматичний матчинг клієнта для telegram_personal

## Статус
done

## Задача
У чаті розмови з каналу `telegram_personal` показувались як `#321803091` замість імені/юзернейма,
і клієнт із CRM не прив'язувався автоматично, навіть коли в його картці записаний той самий
Telegram-нікнейм.

Причина: `telegram_personal.build_inbound_event()` завжди віддавав `contact={}`. Загальний fallback
в `inbox_service._get_or_create_conversation` шукає метод `enrich_contact` — а в
`TelegramPersonalAdapter` схожий метод називався `resolve_contact` (для «Новий діалог»), тож
`hasattr` не спрацьовував. Без імені `Conversation.display_name` падає в `#<external_chat_id>`, а
`client_service.find_client_for_contact` не має за чим шукати клієнта.

Супутні дефекти:
- `ingest_event` оновлював контакт лише `if event.contact:` — порожній dict фолсі, тож імена
  ніколи не «доїжджали» пізніше;
- матчинг на клієнта пробувався тільки в момент створення розмови;
- `_handle_match` не розумів хендл, записаний як посилання (`t.me/name`, `instagram.com/name`).

## План
- [x] `build_inbound_event(message, sender=...)` + `contact_from_entity()` + `enrich_contact()`
- [x] Воркер резолвить sender у живому asyncio-циклі
- [x] `inbox_service`: доповнення контакту на кожній події + відкладений автолінк
- [x] Бекфіл лагодить уже створені розмови без імені
- [x] `_handle_match` розуміє профільні посилання
- [x] Тести

## Реалізація
- `app/services/messaging/telegram_personal.py`
  - `contact_from_entity(entity)` — Telethon User → `{name, username, phone}`.
  - `build_inbound_event(message, sender=None)` — заповнює `contact` із sender'а.
  - `TelegramPersonalAdapter.enrich_contact(channel, external_chat_id)` — резервний пошук через
    `get_entity`, тепер спрацьовує загальний fallback в `inbox_service`.
- `scripts/run_telegram_personal_worker.py` — `sender = await event.get_sender()` перед інжестом
  (тільки тут, усередині живого циклу, це дешево); помилка резолву не блокує збереження
  повідомлення.
- `app/services/messaging/inbox_service.py`
  - `apply_contact(conv, contact)` — доповнює непорожні поля на **кожній** події.
  - `_try_auto_link(conv)` — лінкує клієнта, якщо кандидат рівно один; викликається і при
    створенні розмови, і пізніше, коли з'явився username/телефон. Ручний лінк не перетирається.
- `app/services/messaging/telegram_personal_backfill.py` — після `_get_or_create_conversation`
  дописує контакт наявним розмовам (і пробує автолінк). Діалоги з ботами більше не пропускаються
  повністю: історія бота не імпортується, але якщо розмова вже існує — їй проставляється ім'я.
- `app/services/client_service.py` — `_normalize_handle()`; `_handle_match` матчить хендл,
  `@хендл` і профільні посилання (`t.me/...`, `instagram.com/...`, з/без `https://` і `/` в кінці).

## Як тестувати
1. `python3 -m pytest tests/unit -q` — 442 passed, 3 xfailed.
2. На dev: перезапустити воркер (`docker compose restart telegram-personal-worker` або як він
   називається в compose) — нові вхідні повідомлення мають створювати розмову з іменем контакту.
3. Для вже наявних розмов з `#<id>`: `flask messaging-backfill-telegram-personal <channel_id> --days 1`
   — пройдеться по діалогах, проставить імена/юзернейми і, де можливо, прив'яже клієнта.
   `--days 1` бо історія вже імпортована, потрібні лише контакти.
4. У клієнта з полем Telegram = `oksana_tg` (або `https://t.me/oksana_tg`) розмова з тим самим
   нікнеймом має показати панель клієнта справа замість «Клієнт не прив'язаний».

## Edge cases
- Контакт без username і без телефону (прихований профіль) — буде ім'я, але автолінк не спрацює:
  лінкувати вручну.
- Двоє клієнтів з однаковим хендлом — автолінк свідомо не спрацьовує (ніколи не вгадуємо).
- Розмова, залінкована менеджером вручну, не перелінковується автоматично.
- `enrich_contact` викликаний з живого asyncio-циклу впаде на `asyncio.run` — помилка ковтається і
  повертається `{}`; у воркері цей шлях і не використовується, бо sender передається явно.
- Бекфіл не створює розмов для ботів — лише оновлює ті, що вже створив живий воркер.
