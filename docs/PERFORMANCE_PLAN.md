# Performance — Known Issues

> Аналіз вузьких місць при навантаженні ~100 замовлень/день.

## Пріоритети

| # | Проблема | Файл | Пріоритет | Складність |
|---|----------|------|-----------|------------|
| 1 | `assign_deliveries()` скидає ВСІ доставки в БД (не фільтрує по даті) | `delivery_service.py:~146` | Критичний | Низька |
| 2 | `get_all_clients()` завантажує всіх клієнтів в RAM, пагінація в Python | `client_service.py:6` | Критичний | Середня |
| 3 | Відсутні DB індекси: `delivery_date`, `status`, `courier_id`, `order.client_id` | всі моделі | Критичний | Низька |
| 4 | N+1 запити в шаблонах (cert.order.client, order.deliveries) | templates | Високий | Середня |
| 5 | `_monthly_orders_trend()` — вибірка без ліміту, зростає щомісяця | `reports_service.py:~128` | Високий | Низька |
| 6 | JOIN по `delivery_date` без індексу в `get_orders()` | `order_service.py:~198` | Високий | Низька (вирішується п.3) |
| 7 | Звіти — 8 важких GROUP BY без кешування | `reports_service.py` | Середній | Середня |
| 8 | `active_sub_client_ids` виконується на кожен `/clients` навіть без фільтра | `clients/routes.py:~18` | Низький | Низька |
| 9 | `florist_bulk_update_status()` без rollback при помилці | `florist/routes.py:~91` | Середній | Низька |

## Швидкий виграш (1-2 години роботи)

1. `index=True` на `delivery.delivery_date`, `delivery.status`, `delivery.courier_id`, `order.client_id`
2. Фільтр по даті в `assign_deliveries()` замість `Delivery.query.all()`
3. `_monthly_orders_trend()` — обмежити останніми 12 місяцями
4. `active_sub_client_ids` — обгорнути в `if sub_filter:`
5. `try/except rollback` у florist bulk update
