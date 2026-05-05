# ADR-0002 — Notification service: відкласти до другого адаптера

**Статус:** Прийнято  
**Дата:** 2026-05-05

## Контекст

Потрібні нагадування: менеджеру про продовження підписок, флористам про незакриті доставки. Виникло питання — створити `notification_service` зараз чи пізніше.

## Рішення

**Не створювати `notification_service` зараз.**

Натомість — винести логіку виявлення ("що потребує уваги") у відповідні сервіси:
- `subscription_service.get_subscriptions_needing_renewal(today)`
- `delivery_service.get_overdue_unclosed_deliveries(today)`

## Причини

Зараз один канал доставки нотифікацій — дашборд. One adapter = hypothetical seam.

`notification_service` стає виправданим коли з'явиться другий адаптер — Telegram-нагадування. Тоді:
- detection: ті самі функції в сервісах
- delivery: notification_service координує дашборд + Telegram

## Наслідки

- Дашборд викликає detection-функції з сервісів (не містить власних SQL-запитів)
- Коли додаються Telegram-нагадування — `notification_service` підключається до готових функцій без переписування логіки виявлення
- Не пропонувати `notification_service` до появи другого delivery-каналу
