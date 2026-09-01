# Заморозка цін для існуючих підписок

## Статус
done

## Задача
Зміна цін у довіднику (`/settings/prices`, активний `PricePreset`) не має заднім
числом впливати на вже створені підписки — наступні доставки мають списуватись за
ціною, актуальною на момент створення підписки. Раніше `charge_delivery` для
підписочних замовлень **завжди** рахував ціну наживо і ігнорував збережене
`order.charged_amount`.

## План
- [x] `resolve_charge_amount(order)` — заморожена ціна першою, жива лише як фолбек
- [x] `charge_delivery` і `reconcile_historical_charges` перевести на неї (прибрати спец-гілку для підписок)
- [x] CLI `flask freeze-subscription-prices` — бекфіл `charged_amount` для старих підписок
- [x] Тести
- [x] Перевірка на локальній БД (копія проду)

## Реалізація
- `app/services/billing_service.py`
  - новий `resolve_charge_amount(order)`: `order.charged_amount` якщо є, інакше `get_order_price(order)`
  - `charge_delivery`: гілка `if order.subscription_id: get_order_price(...)` → `resolve_charge_amount(order)`
  - `reconcile_historical_charges`: те саме
- `app/__init__.py` — CLI-команда `freeze-subscription-prices`:
  - для `order` з `subscription_id` та `charged_amount IS NULL`:
    1. якщо по будь-якій доставці замовлення вже є транзакція `delivery_charge` → беремо її суму (реальна історична ціна)
    2. інакше → `get_order_price(order)` (жива ціна з активного прайсу)
  - dry-run за замовчуванням, запис лише з `--commit`
- `tests/unit/test_billing_freeze_price.py` — 3 тести

## Локальна перевірка (БД = копія проду)
- Order 735 (підписка, size L, `charged_amount=2200`): після тестової зміни цін
  `get_order_price` = 22002500, а `resolve_charge_amount` = **2200** ✅
- dry-run бекфілу: 830 підписочних замовлень без `charged_amount` →
  629 заповнюється з наявних транзакцій, 201 — з активного прайсу, 0 пропущено
- `pytest tests/unit` — 329 passed

## Як тестувати
1. Підписка, створена раніше (у `order.charged_amount` є значення).
2. `/settings/prices` — підняти ціну для її розміру, зберегти.
3. Позначити наступну доставку цієї підписки «Доставлено».
4. Очікувано: транзакція `delivery_charge` на **стару** суму (= `order.charged_amount`),
   баланс клієнта зменшується на неї ж.
5. Нова підписка, створена після зміни цін → списується за новою ціною.
6. Разове замовлення → без змін.

## Порядок деплою (важливо!)
1. Змерджити й задеплоїти цей фікс.
2. **Повернути ціни в довіднику до реальних значень** (зараз стоять тестові).
3. `flask freeze-subscription-prices` (dry-run) → перевірити цифри.
4. `flask freeze-subscription-prices --commit`.
5. Тепер виставити потрібні нові ціни в довіднику.

Якщо зробити навпаки (спершу нові ціни, потім бекфіл) — 201 підписка без історії
списань заморозиться на новій ціні.

## Edge cases
- `charged_amount IS NULL` і бекфіл не прогнали → фолбек на живу ціну (як і було).
- Редагування підписки (`subscription_service.py:956`) свідомо перераховує
  `charged_amount` — навмисна зміна ціни користувачем, лишили як є.
- Розмір «Власний» — ціна з `custom_amount`, довідник не читається.
- Знижка клієнта змінилась після створення підписки → списується заморожена сума.
