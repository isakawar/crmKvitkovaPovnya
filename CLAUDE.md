# CLAUDE.md — CRM Kvitkova Povnya

Flask CRM for a flower shop. Manages clients, orders, bouquet subscriptions, deliveries, couriers, and routes. Telegram bot integration for couriers.

---

## 🤖 AI Workflow

1. Analyze the problem
2. Propose a step-by-step plan
3. **Wait for approval**
4. Implement step-by-step
5. Create/update task file in `tasks/` (format: `YYYY-MM-DD_short-description.md`, template in `tasks/README.md`)

**First response — plan only. Do not write code before approval.**

After implementation always: describe how to test, expected behavior, edge cases.

---

## Rules

- Business logic only in `services/` — not in routes or templates
- Extend existing services before creating new ones
- Only touch files relevant to the current task
- Read only relevant files — don't scan the whole project
- If behavior is unclear — ask before implementing

---

## Service Navigation

| Task | File |
|------|------|
| Orders | `app/services/order_service.py` |
| Deliveries | `app/services/delivery_service.py` |
| Clients | `app/services/client_service.py` |
| Route optimization | `app/services/route_optimizer_service.py` |
| CSV import | `app/services/csv_import_service.py` |
| Reports / Statistics / P&L | `app/services/reports_service.py` |

---

## Reports & Statistics Architecture

Page: `/reports` (blueprint: `app/blueprints/reports/`). Tabs: Deliveries, P&L, Export, Cash Flow, Баланс клієнтів.

### Public API — one function per domain

| Function | Returns namespace | Description |
|----------|-------------------|-------------|
| `get_orders_data(date_from_str, date_to_str)` | `orders` | Marketing source, for-whom, delivery type, size breakdowns + 365-day order trend |
| `get_deliveries_analytics(date_from_str, date_to_str)` | `deliveries` | Status KPIs (SQL aggregation), dynamics chart, city distribution |
| `get_pl_data(date_from_str, date_to_str)` | `pl` | Revenue, expenses, profit, margin, expense breakdown by category |
| `get_subscription_renewal_rate(date_from_str, date_to_str)` | `subscriptions` | Renewal rate, renewed/declined/pending counts |
| `get_florist_sales_data(date_from_str, date_to_str)` | `florist` | Offline florist sales with 5% bonus; defaults to current month when no range given |
| `get_client_revenue_breakdown(date_from_str, date_to_str)` | `revenue` | Per-client monthly balance: start balance, Нараховано (delivery_charge), Оплачено (credit), end balance; defaults to last 3 months |

### How the route passes data to the template

```python
return render_template('reports/index.html',
    orders=get_orders_data(date_from, date_to),
    deliveries=get_deliveries_analytics(date_from, date_to),
    pl=get_pl_data(date_from, date_to),
    subscriptions=get_subscription_renewal_rate(date_from, date_to),
    florist=get_florist_sales_data(date_from, date_to),
    active_tab=active_tab,
    date_from=date_from or '',
    date_to=date_to or '',
)
```

Template accesses data via namespace: `{{ deliveries.total }}`, `{{ pl.revenue }}`, `{{ orders.marketing_all_total }}`.

### Adding a new metric — checklist

1. Add the key to the relevant `get_*` function's return dict (no domain prefix needed — namespace comes from the kwarg name in the route).
2. Access it in the template as `{{ namespace.key }}`.
3. If adding a whole new domain: create a new `get_<domain>_data()` function, add it as a kwarg in `routes.py`, use `{{ new_domain.key }}` in the template.

### Key patterns in reports_service.py

- **Label normalization**: `_label_key()` / `_display_label()` — normalizes Ukrainian variants of "not specified" into a single bucket. Use these when aggregating any string column from user input.
- **Chart data format**: always `{'labels': [...], 'values': [...]}` — matches Chart.js expectations.
- **Monthly gap filling**: `_fill_monthly_gaps(month_counts: dict[date, int])` — fills zero-value months between first and last.
- **Status aggregation**: use `func.sum(case((Model.status == 'X', 1), else_=0))` — never load full objects and count in Python.
- **`_rows_to_items(rows)`**: converts `[(raw_label, count)]` query results into `[{'label': str, 'count': int}]` with deduplication and sorting.
- **`_ordered_items(items, preferred_labels)`**: reorders items to match a preferred label order (e.g., from Settings).

### Temporal semantics

All public functions accept `date_from_str` / `date_to_str` (ISO `YYYY-MM-DD` strings or `None`).  
`get_orders_data` returns **two variants** for marketing/for-whom charts: `*_all` (always all-time) and `*_range` (filtered by date range, empty list when no range selected).  
`_monthly_orders_trend()` always shows last 365 days regardless of filter — it is a trend sparkline, not a filtered metric.

### Expense categorization model

```
Transaction (debit)
  └── expense_type_id (FK) → Settings (type='expense_type')
                                └── category_id (FK) → ExpenseCategory
```

Use `expense_type_id` FK — not the legacy `expense_type` string column.

---

## Key Concepts

**Subscriptions** — not a separate model. A subscription is an `Order` with `delivery_type` in `('Weekly', 'Monthly', 'Bi-weekly')`. On creation, 4 deliveries are auto-generated. Requires both type + size.

**Certificates** — types: `amount` (UAH value), `size` (bouquet size), `subscription` (type + size). Auto-expire in 1 year. Status: `active` → `used` after applying to an order.

**Order sizes** — `S`, `M`, `L`, `XL`, `XXL`, `Власний` (requires `custom_amount`).

**Roles** — `admin`/`manager`: full access. `florist`: `/florist` routes only. `courier`: Telegram bot only.

---

## Migrations (gotcha)

**Always find the actual current head before creating a new migration.**

Before writing `down_revision`, run or grep to find which revision has no successor:

```bash
# find current head(s)
grep -r "down_revision" migrations/versions/*.py | grep -v "__pycache__"
# the revision that no other file references as down_revision → that is the head
```

Set `down_revision` to that value. **Never assume** the head is the last migration you worked on — another migration may have been added in between. Creating a branch (two files with the same `down_revision`) causes Alembic multiple-heads error and the container won't start.

---

## DB Table Names (gotcha)

SQLAlchemy uses lowercase class name by default — always verify before writing migrations:

| Model | Table |
|-------|-------|
| `Order` | `order` (not `orders`) |
| `User` | `user` (not `users`) |
| `Client` | `client` |
| `Delivery` | `delivery` |
| `Certificate` | `certificates` (explicit `__tablename__`) |
| `DeliveryRoute` | `delivery_routes` (explicit `__tablename__`) |

---

## Templates

- Toast notifications: `{{ render_toast() }}` + `{{ toast_script() }}` + `showToast('text', 'success'|'error')`
- Date filter: `{{ order.created_at | kyiv_time }}`
- After adding new Tailwind classes to templates — run `npm run build`
- `_composer_script.html` — 40KB JS file, understand before editing

---

## Git

Conventional commits are required — they drive automatic versioning:

```
feat: ...   → minor bump (0.3.0 → 0.4.0)
fix: ...    → patch bump (0.3.0 → 0.3.1)
```

PR merge to `main` → auto tag + GitHub Release. Deploy is manual only (`workflow_dispatch`).
