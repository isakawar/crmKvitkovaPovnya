# Підписка: коментар при редагуванні копіюється на всі доставки

## Статус
done

## Задача
Менеджер: при створенні/редагуванні підписки коментар («коментар») зберігається
на ВСІ доставки. Має лишатись тільки на першій доставці — на всі доставки
поширюються лише «побажання» (`preferences`).

## Причина
`create_subscription` / `extend_subscription` вже ставлять `comment` лише на
перший ордер (`comment ... if i == 0 else None`). Але `update_subscription`
(`subscription_service.py:917`) у циклі по всіх недоставлених ордерах робив
`order.comment = subscription.comment` без обмеження, а далі
`sync_order_to_active_deliveries` штовхав це у `delivery.comment`.

## Реалізація
`app/services/subscription_service.py` — у `update_subscription`:
- перед циклом визначається `first_order` (найраніша недоставлена доставка за
  `delivery_date`, тай-брейк `sequence_number`);
- `order.comment = subscription.comment if order is first_order else None`;
- `preferences` як і раніше — на всі ордери.

## Як тестувати
1. `pytest tests/unit/test_subscription_creation.py -k comment`
2. Вручну: створити підписку з коментарем → відредагувати підписку, змінити
   коментар і побажання → у списку доставок коментар лише на першій майбутній,
   побажання на всіх.

## Edge cases
- Перша доставка вже «Доставлено» → `first_order` = наступна недоставлена.
- Індивідуальне редагування ордера (`update_order`) не зачеплено — там коментар
  лишається по-ордерним.
