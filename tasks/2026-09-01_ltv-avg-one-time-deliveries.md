# LTV: середня кількість разових доставок на клієнта

## Статус
done

## Задача
Нова метрика на вкладці «LTV та Клієнти»: скільки в середньому разових доставок
припадає на клієнта, який хоч раз оформлював разову доставку.

- разова доставка = `Delivery`, чий `Order.subscription_id IS NULL`
- знаменник = унікальні клієнти з ≥1 разовою доставкою (без «Скасовано»)
- клієнт із підписками + разовою — рахується; лише з підписками — ні

## Реалізація
- `app/services/reports_service.py` → `get_ltv_data`: запит `one_time_del`,
  нові ключі `avg_one_time_deliveries_per_client`, `one_time_deliveries_total`,
  `one_time_clients_count`.
- `app/templates/reports/index.html`: 4-та `kpi-card` у блоці LTV, поруч із
  «Сер. час з нами».
- `CLAUDE.md`: оновлено опис `get_ltv_data`.
- `tests/unit/test_reports_ltv_one_time.py`.

## Як тестувати
1. `pytest tests/unit/test_reports_ltv_one_time.py`
2. `/reports?tab=clients` → картка «Сер. разових доставок / клієнта» з підписом
   «N разових доставок / M клієнтів з разовою».

## Edge cases
- Клієнт лише з підписками → не в знаменнику.
- Скасована разова доставка → не рахується (узгоджено з іншими LTV-метриками).
- Немає жодної разової доставки → метрика 0.0.
