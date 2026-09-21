# Fix: get_thread повертав повідомлення у зворотному порядку

## Статус
done

## Задача
Під час підготовки демо-скріншотів для `/inbox` (насіяв тестові дані,
відкрив тред) виявив, що повідомлення рендерились новіші-згори,
старіші-знизу — навпаки нормальної хронології чату.

## Причина
`Conversation.messages` — dynamic-зв'язок з уже вбудованим
`order_by='Message.id'` (ASC). `get_thread()` для початкової сторінки й
для `before_id`-пагінації додавав `.order_by(Message.id.desc())` **поверх**
цього, не скидаючи попереднє сортування. SQLAlchemy при повторному
`.order_by()` не замінює критерій, а додає до нього — фінальний SQL ставав
`ORDER BY id ASC, id DESC`. Оскільки `id` унікальний, перший критерій
(ASC) повністю визначає порядок, і `.desc()` мовчки ігнорувався. Замість
"останні N повідомлень" запит фактично повертав "перші N" (найстаріші),
а потім `.reverse()` розвертав саме цю (неправильну) вибірку.

Перевірив прямо на SQL (`.statement.compile(literal_binds=True)`) —
`ORDER BY messaging_message.id, messaging_message.id DESC` підтвердив
здогад.

Наслідки в проді: для розмови з ≤50 повідомлень — просто зворотний
порядок на екрані (видно все, але задом наперед). Для розмови з >50 —
гірше: показало б перші 50 найстаріших замість останніх 50, тобто
менеджер відкриває тред і не бачить нещодавніх повідомлень.

## Реалізація
`app/services/messaging/inbox_service.py::get_thread` — `.order_by(None)`
перед `.order_by(Message.id.desc())`, щоб скинути успадкований ASC-критерій
з relationship перед застосуванням власного.

Тести (`tests/unit/test_messaging_inbox_service.py`, 3 нових):
- `test_get_thread_initial_page_is_chronological_not_reversed` — 5
  повідомлень, `limit=3` → очікує `['c','d','e']` (останні 3,
  хронологічно), `has_more=True`.
- `test_get_thread_no_pagination_needed_when_under_limit`
- `test_get_thread_before_id_page_is_chronological`

## Як тестувати
`pytest tests/unit/test_messaging_inbox_service.py -k get_thread` — 3 нових
тести, усі проходять. Повний messaging-набір — 57 проходять.
Візуально підтверджено на локальному dev-сервері з насіяними даними —
скріншот до/після фіксу показав правильний хронологічний порядок.

## Edge cases
- `after_id`-гілка (полінг нових повідомлень) цим багом не була уражена —
  там `.order_by(Message.id)` (ASC) збігається з успадкованим ASC, тож
  додавання не міняло результат.
