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
| Reports | `app/services/reports_service.py` |

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
