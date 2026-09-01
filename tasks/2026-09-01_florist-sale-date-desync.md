# Офлайн-продаж: дата в звітах не збігається з датою транзакції

## Статус
done

## Задача
Після редагування дати транзакції «Офлайн продаж» (напр. з 01.09 на 31.08) продаж
зникав із «Виручки» (P&L) і з бонусу флориста за серпень — бо звіти рахували дату
по незмінному `FloristSale.created_at`, а не по редагованому `Transaction.date`.

## План
- [x] Ввести `_florist_sale_date_col()` — `coalesce(Transaction.date, date(FloristSale.created_at))`
- [x] `get_pl_data`: `florist_total` та `prev_florist` — outerjoin Transaction + новий колонковий вираз
- [x] `get_florist_sales_data`: те саме
- [x] Тести

## Реалізація
`app/services/reports_service.py`:
- Додано хелпер `_florist_sale_date_col()` (після `_build_date_filters`).
- `get_pl_data` — обидва запити суми офлайн-продажів тепер `outerjoin(Transaction)`
  і фільтруються по `_florist_sale_date_col()`.
- `get_florist_sales_data` — так само (+ імпорт `Transaction`).

Дата транзакції = єдине джерело правди (як і в Cash Flow). Записи без
`transaction_id` (легасі) продовжують рахуватись по `created_at`.

`tests/unit/test_reports_florist_sale_date.py` — новий файл.

## Як тестувати
1. `pytest tests/unit/test_reports_florist_sale_date.py`
2. Вручну: створити офлайн-продаж сьогодні → відредагувати дату його транзакції
   на минулий місяць → у `/reports` за минулий місяць продаж має бути і у
   «Виручці», і у вкладці бонусів флористів; за поточний місяць — зникнути.

## Edge cases
- Легасі-продаж без транзакції → fallback на `created_at` (тест покриває).
- Форма редагування продажу у флориста поля дати не має — дату міняє лише
  адмін/менеджер через сторінку транзакцій. Список продажів флориста і вікно
  редагування 24h навмисно лишились на `created_at`.
