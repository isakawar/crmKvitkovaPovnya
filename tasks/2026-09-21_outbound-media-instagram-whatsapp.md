# Вихідні медіа для Instagram і WhatsApp

## Статус
done

## Задача
`send_media()` для Instagram і WhatsApp завжди повертав `ok=False` — вихідні
вкладення (фото) не працювали на цих двох каналах (Telegram обидва вміли,
Viber лишається поза скоупом цієї задачі). Стара причина в докстрінгах
("потрібен публічний URL") виявилась застарілою — обидві Meta-платформи
мають спосіб завантажити бінарник напряму, без публічного URL.

## План
- [x] Перевірити в документації Meta, чи справді Instagram Send API вимагає
  публічний URL, чи є прямий binary-upload (WebFetch на офіційні доки)
- [x] Спільний хелпер нормалізації зображення в JPEG (Meta не приймає heic;
  WhatsApp приймає лише jpeg/png)
- [x] WhatsApp: `POST /{phone_number_id}/media` → `media_id` →
  `POST /{phone_number_id}/messages` з `image.id`/`image.caption`
- [x] Instagram: Attachment Upload API (`POST /{page_id}/message_attachments`,
  `is_reusable`) → `attachment_id` → `POST /{ig_id}/messages`
- [x] Instagram caption — best-effort follow-up текстове повідомлення
  (Messenger/IG attachment-повідомлення не підтримують інлайн-caption)
- [x] Оновити тести (`test_send_media_not_supported` → реальні кейси)
- [x] Оновити CLAUDE.md (застарілі нотатки "text-only")

## Реалізація
- `app/services/messaging/media_convert.py` (новий) — `to_jpeg_bytes(file_path)`,
  той самий Pillow + pillow-heif патерн, що вже є в `app/services/photo_service.py`
  (`_to_webp`), тільки в JPEG замість webp — під формат, який гарантовано приймають
  обидві Meta-платформи.
- `app/services/messaging/whatsapp.py` `send_media()`:
  1. `POST /{channel.external_id}/media` (multipart, `messaging_product=whatsapp`,
     `type=image/jpeg`, `file=<jpeg-байти>`) → `id`.
  2. `POST /{channel.external_id}/messages` з `type=image`, `image={id, caption?}`
     (WhatsApp підтримує caption нативно в об'єкті `image`).
- `app/services/messaging/instagram_dm.py` `send_media()`:
  1. `POST /{channel.fb_page_id}/message_attachments` (multipart, `message` —
     JSON `{"attachment":{"type":"image","payload":{"is_reusable":true}}}`,
     `filedata=<jpeg-байти>`) → `attachment_id`. **Важливо**: цей ендпоінт іде
     через `fb_page_id`, не через IG-акаунт-id (`channel.external_id`) — той
     лишається для власне відправлення повідомлення.
  2. `POST /{channel.external_id}/messages` з `attachment.payload.attachment_id`.
  3. Якщо був `caption` — окремий `send_text()` одразу після (best-effort,
     не валить результат, якщо не вдалось — фото вже пішло).
- Перевірено через `WebFetch` на офіційну документацію Meta (`developers.facebook.com`)
  перед реалізацією — і Instagram Attachment Upload API, і WhatsApp Media Upload API
  підтверджені як реальні, задокументовані ендпоінти (не здогадка).
- Тести: `tests/unit/test_messaging_whatsapp_adapter.py` і
  `test_messaging_instagram_adapter.py` — `test_send_media_not_supported` замінено
  на `test_send_media_requires_connected_channel` / `test_send_media_uploads_then_sends`
  / `test_send_media_fails_when_upload_errors` (+ `test_send_media_sends_caption_as_followup_text`
  для Instagram). Реальні тестові JPEG генеруються через Pillow у `tmp_path`, а не
  фейковий `/tmp/x.jpg`, — інакше `media_convert.to_jpeg_bytes` впав би на невалідному файлі.
- `CLAUDE.md` — оновлені нотатки по обох каналах (більше не "text-only"), і
  виправлено кількість тестів (49 → 65) та список каналів без покриття
  (Viber насправді покритий, лишився тільки `telegram_personal`).

## Як тестувати
1. `python3 -m pytest tests/unit/test_messaging_whatsapp_adapter.py tests/unit/test_messaging_instagram_adapter.py -q`
   — усі проходять локально (без реального Meta App, тести мокають `requests.post`).
2. **Живий тест неможливий без реального Meta App** (той самий блокер, що й раніше
   для решти Facebook-флоу) — коли клієнт створить App і підключить канали через
   `/settings/messaging`, перевірити вручну: відповісти фото в Instagram/WhatsApp
   тред з `/inbox`, переконатись що контакт отримав картинку (і підпис під нею
   для WhatsApp; для Instagram — картинка + окреме текстове повідомлення з підписом).

## Edge cases
- Вхідний файл `heic` (iPhone) — конвертується в JPEG перед відправкою; якщо
  Pillow не може відкрити файл (пошкоджений/невідомий формат) — `send_media`
  повертає `ok=False` з поясненням, не кидає виняток нагору.
- Instagram caption success/fail незалежні: якщо фото пішло, а follow-up текст
  з підписом впав (мережа/rate limit) — `send_reply` все одно бачить `ok=True`
  для фото; підпис у самому CRM (`Message.text`) лишається видимим менеджеру
  незалежно від того, чи дійшов він до контакту в Instagram.
- WhatsApp `image.caption` — нативна підтримка Meta, без обхідних шляхів.
- Attachment ID в Instagram протухає через 90 днів (за докою Meta) — не
  проблема тут, бо кожен виклик `send_media` завантажує заново, ніде не кешує
  `attachment_id` між викликами.
