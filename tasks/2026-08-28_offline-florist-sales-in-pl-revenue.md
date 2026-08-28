# Офлайн продажі флористів у Revenue (вкладка P&L)

## Проблема
`pl.revenue` рахувався лише як сума транзакцій `delivery_charge`. Офлайн-продажі
флористів (`FloristSale`) — це теж продажі, але вони не потрапляли в Revenue і в
блок «Розбивка Revenue».

## Зміни
`app/services/reports_service.py`:
- `get_pl_data()` — рахує `florist_total` = сума `FloristSale.amount` за той самий
  діапазон дат (фільтр по `func.date(FloristSale.created_at)`).
  `revenue = delivery_charge_revenue + florist_total`. `profit` / `margin`
  перераховуються автоматично.
- `revenue_per_delivery` навмисно лишили на базі `delivery_charge_revenue`
  (це метрика по доставках).
- `_build_revenue_breakdown(d_from, d_to, total_revenue, florist_total=0)` —
  додає рядок «Офлайн продажі (флористи)» після «Разові замовлення».
  Секція «Розміри» лишається лише по доставках (у FloristSale немає розміру).

Шаблон не змінювався.

## Як тестувати
1. `/reports?tab=pl` з діапазоном, де є офлайн-продажі.
2. Revenue виріс рівно на суму `FloristSale.amount` за період.
3. У розбивці Revenue зʼявився рядок «Офлайн продажі (флористи)» з коректним %.
4. Profit виріс на ту саму суму.
5. Період без офлайн-продажів — поведінка без змін (рядок не показується).
