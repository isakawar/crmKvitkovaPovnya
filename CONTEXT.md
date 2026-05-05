# Domain Glossary — CRM Kvitkova Povnya

Use these terms exactly when discussing or modifying architecture. Consistent language prevents concept drift.

---

## Підписка (Subscription)

Сутність що об'єднує N замовлень-доставок для одного клієнта. Підписка — єдиний об'єкт протягом усього свого життя; нові цикли додаються до неї, нова підписка не створюється.

Model: `Subscription` → table `subscription`

---

## Цикл (Cycle)

Група доставок в рамках однієї підписки. Перший цикл — 4 доставки при створенні. Кожне продовження додає новий цикл (ще 4 доставки). Номер циклу зберігається на кожному замовленні: `Order.cycle_number`.

Цикл 1 → `sequence_number` 1–4, `cycle_number=1`  
Цикл 2 → `sequence_number` 5–8, `cycle_number=2`  
і т.д.

---

## Продовження (Extension)

Додавання нового циклу до існуючої підписки. Єдина точка входу: `extend_subscription(subscription, overrides=None)` в `subscription_service.py`.

`overrides` — словник полів що клієнт змінив при продовженні (адреса, коментар, дата тощо). Якщо `None` — параметри копіюються з підписки.

Продовження **не** створює нову підписку і **не** ставить `is_extended=True`.

---

## Нагадування про продовження (Renewal Reminder)

Сигнал що підписка потребує нового циклу. Виявляється функцією `get_subscriptions_needing_renewal(today)` в `subscription_service.py`.

Умова: остання дата доставки була 4+ днів тому, `followup_status` is None або `'pending'`, snooze не активний.

Дашборд відображає ці підписки у черзі "Продовжити". Telegram-нагадування — майбутній другий адаптер.

---

## Тип підписки (Subscription Type)

Одне з: `Weekly`, `Bi-weekly`, `Monthly`. Єдине визначення: `SUBSCRIPTION_TYPES` в `subscription_service.py`.

---

## Нагадування з імпорту (Import Reminder)

Підписки що потрапили через CSV-імпорт з `delivery_number >= 5` — вже минулий цикл, замовлення не створювались. Позначаються `is_renewal_reminder=True`. Окрема секція на дашборді.
