# KPI-картка «Рекордний день» на вкладці Cash Flow

## Статус
done

## Задача
Додати на вкладку Cash Flow (`/reports?tab=cash_flow`) ще один KPI-показник —
день з найбільшою сумою надходжень (`credit`-транзакції) за весь час: велика
сума + дрібним знизу дата і к-сть клієнтів того дня. Розміщення — четверта
картка в ряду (див. `tasks/assets/2026-08-27_cashflow-record-day.png`).

## Реалізація

### app/services/reports_service.py
- Новий хелпер `_cash_flow_record_day()`: один запит —
  `SUM(amount)` та `COUNT(DISTINCT client_id)` по `transaction` де
  `transaction_type='credit'`, `GROUP BY date`, `ORDER BY SUM(amount) DESC, date DESC`,
  `LIMIT 1`. Повертає `record_day_amount`, `record_day_date` (`%d.%m.%Y` або `—`),
  `record_day_clients`.
- `get_cash_flow_data` стала тонкою обгорткою: викликає `_get_cash_flow_data`
  (стара логіка, перейменована) і мержить у результат `_cash_flow_record_day()`.
  Показник **не залежить від фільтра** — це рекорд за весь час.

### app/templates/reports/index.html
- Додано 4-ту `.kpi-card` у `#tab-cash_flow` після картки «Динаміка».
  `.kpi-grid` уже 4-колонковий. Нових Tailwind-класів немає → build не потрібен.

## Як тестувати
1. Перезапустити web (gunicorn без reload): `docker compose restart web`.
2. `/reports?tab=cash_flow` → картка «Рекордний день» показує максимальний денний
   `credit`-підсумок, знизу дата + «N клієнт(ів) · за весь час».
3. Змінити місяць/діапазон угорі → перші 3 картки й графік перераховуються,
   «Рекордний день» лишається незмінним.

## Edge cases
- Немає `credit`-транзакцій → `₴0`, дата `—`, без блоку клієнтів.
- Кілька днів з однаковою сумою → береться найсвіжіший (`ORDER BY ..., date DESC`).
- Транзакції без `client_id` → не рахуються у `COUNT(DISTINCT client_id)`.
