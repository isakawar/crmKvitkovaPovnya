# Subscription Lifecycle Refactor

**Дата:** 2026-05-05  
**Гілка:** refactoring/architecture  
**ADR:** ADR-0001, ADR-0002

## Мета

Уніфікувати lifecycle підписки: один об'єкт, цикли, єдина точка входу для продовження, detection-функції в сервісах.

---

## Кроки

### 1. Міграція: `cycle_number` на `Order`

- Знайти поточний head міграції (`grep down_revision`)
- Додати колонку `Order.cycle_number: Integer, nullable=True`
- Backfill: для існуючих замовлень підписок встановити `cycle_number = (sequence_number - 1) // 4 + 1` де `sequence_number` не null

### 2. `SUBSCRIPTION_TYPES` — одне визначення

- Залишити в `subscription_service.py`
- Видалити з `order_service.py`
- `orders/routes.py`: змінити імпорт з `order_service` на `subscription_service`

### 3. Оновити `create_subscription()`

- При створенні початкових замовлень встановити `cycle_number=1`

### 4. Оновити `extend_subscription(subscription, overrides=None)`

- Прийняти опціональний `overrides: dict | None`
- При створенні нових замовлень: `cycle_number = max(existing cycle_numbers) + 1`
- Застосувати `overrides` до полів нових замовлень і доставок (адреса, коментар, дата, тощо)
- **Видалити** `subscription.is_extended = True`
- **Видалити** `subscription.followup_status = 'extended'`
- **Видалити** guard `if subscription.is_stopped: raise` → залишити (це валідна перевірка)
- **Видалити** guard `if subscription.is_extended: raise ValueError` → більше не потрібен

### 5. Уніфікація Flow 1 (дашборд → форма → сабміт)

В `orders/routes.py`, обробник `POST /orders/new`:
- Якщо `extend_from_order_id` присутній і `is_subscription=True`:
  - Знайти батьківську підписку через `parent_order.subscription_id`
  - Зібрати `overrides` з форми
  - Викликати `extend_subscription(parent_sub, overrides=overrides)`
  - **Не** створювати нову підписку
  - **Не** ставити `parent_sub.is_extended = True` (рядки 297–299 — видалити)
  - Рядок 301 (`is_renewal_reminder=False`) — залишити, це потрібно

### 6. Detection-функції

**`subscription_service.py`** — додати:
```python
def get_subscriptions_needing_renewal(today):
    # SQL-логіка з dashboard/routes.py рядки 111–148
    # Повертає list[dict] або list[Subscription]
```

**`delivery_service.py`** — додати:
```python
def get_overdue_unclosed_deliveries(today):
    # Доставки з минулою датою і статусом != 'Доставлено'/'Скасовано'
```

### 7. Оновити `dashboard/routes.py`

- Замінити inline SQL-запит (рядки 111–148) на виклик `get_subscriptions_needing_renewal(today)`
- Залишити секцію `is_renewal_reminder` (import reminders) без змін

### 8. Відобразити `cycle_number` в UI

**Сторінка підписок** (`templates/subscriptions/`):
- На картці підписки показати "Круг N" поточного активного циклу

**Сторінка замовлень** (`templates/orders/`):
- На картці замовлення показати "Круг N" якщо `order.cycle_number > 1` (або завжди)

---

## Тестування

1. Створити підписку → замовлення мають `cycle_number=1`
2. Продовжити через кнопку в модалці → нові замовлення `cycle_number=2`, підписка не зникає з потенційного списку майбутніх нагадувань
3. Дочекатись (або симулювати) що останнє замовлення циклу 2 минуло → підписка знову з'являється в дашборді
4. Продовжити через дашборд з зміною адреси → нові замовлення мають нову адресу, `cycle_number=3`
5. `SUBSCRIPTION_TYPES` — перевірити що нова підписка створюється коректно

## Edge cases

- Підписка з `sequence_number` що не кратний 4 (наприклад імпорт з нестандартною кількістю) → backfill міграція має обробити через floor division
- `overrides` з частковими полями → незазначені поля беруться з підписки
- Зупинена підписка (`is_stopped=True`) → `extend_subscription` кидає ValueError, не продовжувати
