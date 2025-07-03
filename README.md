# Kvitkova CRM

## Структура проекту

- app.py — точка входу
- config.py — налаштування
- models/ — SQLAlchemy моделі
- routes/ — Flask Blueprints (orders, clients, deliveries, prices)
- services/ — бізнес-логіка (order_service.py)
- utils/ — допоміжні функції (date_utils.py)
- templates/ — Jinja2 шаблони
- static/ — CSS, JS, зображення
- migrations/ — Alembic міграції
- tests/ — автотести

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask db upgrade
python3 app.py
```

## Тестування

```bash
pytest
```

## Додавання бізнес-логіки
- Всі складні операції (створення замовлення, доставок, перевірка кредитів) — у services/order_service.py
- Для роботи з датами — utils/date_utils.py

## Міграції

```bash
flask db migrate -m "comment"
flask db upgrade
```

## Logging
- Весь лог — через logging (info/warning/error)
- Для production можна додати логування у файл logs/app.log 