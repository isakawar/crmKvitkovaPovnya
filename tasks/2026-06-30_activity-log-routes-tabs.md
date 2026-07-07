# Розширення логування + вкладки на /activity-log

## Статус
done

## Задача
Додати логування маршрутів (create/edit/assign/send/status/delete/start_time), підписок (stop/resume), видалення клієнтів і зміни статусів доставок. Реорганізувати /activity-log на вкладки.

## Реалізація

### Нові entity_type
- `route` — маршрути
- `delivery` — статуси доставок

### Нові action значення
- `send` — відправка маршруту кур'єру
- `status_change` — зміна статусу маршруту
- `stop` — зупинка підписки
- `resume` — відновлення підписки

### Змінені файли
- `app/services/route_service.py` — логування create/edit в `save_routes()` з переліком доставок у stops
- `app/blueprints/routes/routes.py` — логування assign, send (taxi+telegram), start_time, status_change, delete
- `app/blueprints/subscriptions/routes.py` — логування stop і resume
- `app/blueprints/clients/routes.py` — логування delete з before_data snapshot
- `app/services/delivery_service.py` — логування переходу в Доставлено/Скасовано
- `app/blueprints/activity_log/routes.py` — tabs (TAB_ENTITY_MAP), нові ENTITY_LABELS і ACTION_LABELS
- `app/templates/activity_log/index.html` — рядок вкладок зверху, нові кольори badge

## Як тестувати
1. `/routes` → зберегти маршрут → `/activity-log?tab=routes` — має бути запис `create` з доставками
2. Призначити кур'єра → з'явився `edit` (зміна кур'єра)
3. Відправити маршрут кур'єру → `send`
4. Змінити статус маршруту → `status_change`
5. Видалити маршрут → `delete` з before_data
6. Вкладки на `/activity-log` — кожна показує тільки свій тип
7. Зупинити підписку → вкладка Підписки, action=stop
8. Відновити підписку → action=resume
9. Видалити клієнта → вкладка Клієнти, action=delete
10. Змінити статус доставки на Доставлено/Скасовано → вкладка Доставки
