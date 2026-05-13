# Логіка білінгу: ціна, знижка, списання кредитів

## Загальна схема

```
Підписка / Замовлення
  └── Order.discount (%)        ← знижка фіксується тут
  └── Order.charged_amount      ← ціна після знижки (фіксується при створенні)
        ↓
    [Доставка виконана]
        ↓
  charge_delivery(delivery)     ← billing_service.py
        ↓
  Transaction(delivery_charge)  ← запис у БД
  Client.credits -= amount      ← баланс клієнта зменшується
```

---

## Моделі

### `Client` (`app/models/client.py`)
| Поле | Тип | Опис |
|------|-----|------|
| `credits` | `Numeric(10,2)` | Поточний баланс клієнта. Збільшується при поповненні (`credit`), зменшується при кожній виконаній доставці (`delivery_charge`). |

### `Order` (`app/models/order.py`)
| Поле | Тип | Опис |
|------|-----|------|
| `size` | `String(32)` | Розмір букету: `S`, `M`, `L`, `XL`, `XXL`, `Власний` |
| `custom_amount` | `Integer` | Ціна вручну — тільки якщо `size == 'Власний'` |
| `charged_amount` | `Integer` | Фіксована ціна після знижки. Встановлюється при створенні замовлення через `get_order_price()`. |
| `discount` | `Integer` | Знижка у відсотках (наприклад `10` = 10%). Копіюється з `Subscription.discount` при створенні. |
| `subscription_id` | `Integer FK` | `NULL` для разового замовлення, заповнений — підписка. |

### `Subscription` (`app/models/subscription.py`)
| Поле | Тип | Опис |
|------|-----|------|
| `discount` | `Integer` | Знижка для всієї підписки (%). Копіюється в кожен `Order` при створенні та продовженні. |
| `size` | `String(32)` | Розмір по замовчуванню для всіх доставок. |
| `custom_amount` | `Integer` | Кастомна ціна, якщо `size == 'Власний'`. |

### `Transaction` (`app/models/transaction.py`)
| Поле | Тип | Опис |
|------|-----|------|
| `transaction_type` | `String(16)` | `'credit'` — поповнення, `'debit'` — витрата, `'delivery_charge'` — автоматичне списання за доставку |
| `amount` | `Numeric(10,2)` | Сума транзакції |
| `client_id` | `Integer FK` | Клієнт, якого стосується транзакція |
| `delivery_id` | `Integer FK` | Прив'язка до конкретної доставки (тільки для `delivery_charge`) |
| `payment_type` | `String(32)` | `'monobank'` або `'cash'` — тільки для `credit` транзакцій |
| `payment_account_id` | `Integer FK` | Рахунок оплати (з таблиці `settings`) |
| `date` | `Date` | Дата транзакції |

### `Price` (`app/models/price.py`)
| Поле | Тип | Опис |
|------|-----|------|
| `preset_id` | `FK → price_presets` | Прив'язка до прайс-листа |
| `order_type` | `String(20)` | `'one_time'` або `'subscription'` |
| `size_id` | `FK → settings` | Розмір (через `Settings.type = 'size'`) |
| `price` | `Integer` | Ціна в гривнях |

### `PricePreset` (`app/models/price_preset.py`)
| Поле | Тип | Опис |
|------|-----|------|
| `is_active` | `Boolean` | Тільки один пресет активний одночасно. `get_order_price()` завжди бере перший активний. |

---

## Функції

### `get_order_price(order)` — `billing_service.py`

Розраховує ціну замовлення після знижки. **Не записує нічого в БД.**

```
якщо order.size == 'Власний':
    base = order.custom_amount

інакше:
    preset = PricePreset де is_active=True
    size_setting = Settings де type='size', value=order.size
    order_type = 'subscription' якщо order.subscription_id else 'one_time'
    price_entry = Price(preset_id, order_type, size_id)
    base = price_entry.price

    якщо підписка:
        base = base / 4      ← ціна прайсу — за місяць, ділимо на 4 доставки

discount = order.discount or 0
return int(base * (1 - discount / 100))
```

**Важливо:** для підписок `Price.price` зберігає місячну вартість, тому ділиться на 4 щоб отримати ціну за одну доставку.

---

### `charge_delivery(delivery)` — `billing_service.py`

Викликається автоматично при зміні статусу доставки на `'Доставлено'`.

1. Перевіряє, чи вже існує `Transaction(delivery_charge)` для цієї доставки — якщо так, пропускає (ідемпотентно).
2. Розраховує суму:
   - Підписка → `get_order_price(order)` (завжди з прайсу, ігнорує `charged_amount`)
   - Разове → `order.charged_amount` або `get_order_price(order)` як fallback
3. Створює `Transaction(transaction_type='delivery_charge', amount=amount, delivery_id=delivery.id)`
4. `client.credits -= amount`

```python
# Де викликається:
# delivery_service.py → set_delivery_status(d, 'Доставлено')
# telegram_bot/handlers.py → підтвердження кур'єром
```

---

### `set_delivery_status(d, new_status)` — `delivery_service.py`

Точка входу для зміни статусу доставки. При `new_status == 'Доставлено'`:
- Фіксує `d.delivered_at = datetime.utcnow()`
- Викликає `charge_delivery(d)` → списання з балансу

---

## Як знижка потрапляє в замовлення

### При створенні підписки (`create_subscription` — `subscription_service.py`)
```python
discount_raw = (form.get('discount') or '').strip()
discount = int(discount_raw) if discount_raw else None

subscription = Subscription(discount=discount, ...)

for i, d_date in enumerate(dates):
    order = Order(discount=subscription.discount, ...)  # ← копіюється
```

`charged_amount` **не встановлюється** при звичайному `create_subscription` — для підписок ціна завжди перераховується через `get_order_price()` в момент списання.

### При імпорті (`create_subscription_from_import`)
```python
order = Order(discount=subscription.discount, ...)
order.charged_amount = get_order_price(order)  # ← фіксується відразу
```

### При продовженні підписки (`extend_subscription`)
```python
order = Order(
    discount=overrides.get('discount') if 'discount' in overrides else subscription.discount,
    ...
)
order.charged_amount = get_order_price(order)  # ← фіксується
```
Якщо в `overrides` є ключ `'discount'`, використовується нове значення; інакше — зі старої підписки.

---

## Поповнення балансу (кредити)

Ручне поповнення — через `POST /transactions/add` (`transactions/routes.py`):
```python
txn = Transaction(transaction_type='credit', amount=amount_val, payment_type=..., ...)
client.credits += amount_val
```

`payment_type`: `'monobank'` або `'cash'`.

---

## Баланс клієнта: що впливає на `Client.credits`

| Операція | Зміна `credits` | Де |
|----------|-----------------|----|
| Ручне поповнення | `+amount` | `transactions/routes.py:266` |
| Редагування транзакції | `+/-delta` | `transactions/routes.py:340` |
| Виконана доставка | `-amount` | `billing_service.charge_delivery` |
| Ручне коригування charged | `-delta_charged` | `reports/routes.py:84` |

---

## Типи транзакцій

| `transaction_type` | Хто створює | Відображається в журналі |
|--------------------|------------|--------------------------|
| `credit` | Менеджер вручну | Так |
| `debit` | Менеджер вручну (витрати) | Так |
| `delivery_charge` | Автоматично при статусі `Доставлено` | Ні (фільтрується в `/transactions`) |

`delivery_charge` прихований у журналі транзакцій (`Transaction.transaction_type != 'delivery_charge'`), але враховується у балансі клієнта і в звітах (Cash Flow, Баланс клієнтів).
