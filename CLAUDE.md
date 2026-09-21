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
| Billing (charge / reversal / price freeze) | `app/services/billing_service.py` |
| Transactions & client balance | `app/services/transaction_service.py` |
| Route optimization | `app/services/route_optimizer_service.py` |
| CSV import | `app/services/csv_import_service.py` |
| Reports / Statistics / P&L | `app/services/reports_service.py` |
| Omnichannel inbox / chat | `app/services/messaging/` |

---

## Reports & Statistics Architecture

Page: `/reports` (blueprint: `app/blueprints/reports/`). Tabs (v2): **Огляд / P&L** (`overview` — P&L + Cash Flow), **Доставки та Продажі** (`sales`), **LTV та Клієнти** (`clients`), **Баланс клієнтів** (`balance`). A 4-card hero grid (`get_dashboard_kpis` → `kpis`) sits above the tabs. Export is a header dropdown, not a tab. Legacy `?tab=` values (deliveries/pl/cash_flow/export/revenue/wedding_ltv) are mapped in `routes.py`. Scoped palette lives under `.reports-v2` in `index.html`'s style block.

### Public API — one function per domain

| Function | Returns namespace | Description |
|----------|-------------------|-------------|
| `get_orders_data(date_from_str, date_to_str)` | `orders` | Marketing source, for-whom, delivery type, size breakdowns + 365-day order trend |
| `get_deliveries_analytics(date_from_str, date_to_str)` | `deliveries` | Status KPIs (SQL aggregation), dynamics chart, city distribution |
| `get_pl_data(date_from_str, date_to_str)` | `pl` | Revenue, expenses, profit, margin, expense breakdown by category |
| `get_subscription_renewal_rate(date_from_str, date_to_str)` | `subscriptions` | Renewal rate, renewed/declined/pending counts |
| `get_florist_sales_data(date_from_str, date_to_str)` | `florist` | Offline florist sales with 5% bonus; defaults to current month when no range given |
| `get_client_revenue_breakdown(date_from_str, date_to_str)` | `revenue` | Per-client monthly balance: start balance, Нараховано (delivery_charge), Оплачено (credit), end balance; defaults to last 3 months |
| `get_dashboard_kpis(date_from_str, date_to_str, pl=None)` | `kpis` | The 4 hero cards above the tabs: revenue (+`revenue_growth_pct` vs previous equal-length period, `None` for all-time), profit (+margin), deliveries done (+in progress), active subscriptions (+new in range). Pass an already-computed `pl` dict to skip recomputing `get_pl_data`. |
| `get_wedding_analytics(date_from_str, date_to_str)` | `wedding` | Wedding-subscription KPIs: revenue (delivery_charge), payments (credit linked to sub), deliveries done, orders, avg collected per sub, max deliveries on one sub, revenue share. Range filters revenue/payments/deliveries/orders; `active_count` + `max_deliveries_single_sub` are all-time |
| `get_ltv_data(date_from_str, date_to_str)` | `ltv` | Lifetime-value metrics, all all-time (range ignored): avg deliveries per client (subscription-only, total, and one-time-only — the last averaged over clients with ≥1 non-cancelled one-time delivery), top-10 clients by deliveries, top-10 by revenue, avg lifespan (active client: first delivery → today; churned: first → last delivery), lifespan by subscription periodicity |

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

Template accesses data via namespace: `{{ deliveries.total }}`, `{{ pl.revenue }}`, `{{ orders.marketing_total }}`.

### Adding a new metric — checklist

1. Add the key to the relevant `get_*` function's return dict (no domain prefix needed — namespace comes from the kwarg name in the route).
2. Access it in the template as `{{ namespace.key }}`.
3. If adding a whole new domain: create a new `get_<domain>_data()` function, add it as a kwarg in `routes.py`, use `{{ new_domain.key }}` in the template.

### Key patterns in reports_service.py

- **Label normalization**: `_label_key()` / `_display_label()` — normalizes Ukrainian variants of "not specified" into a single bucket. Use these when aggregating any string column from user input.
- **Chart data format**: always `{'labels': [...], 'values': [...]}` — matches Chart.js expectations.
- **Long-tail grouping**: `_group_small_items(items, other_label, min_pct=2.5, keep_top=None)` — folds small buckets into one "Інші"/"Інші міста"/"Інше" row. Applied to city / marketing-source / for-whom charts. `items` must be sorted count-desc.
- **Monthly gap filling**: `_fill_monthly_gaps(month_counts: dict[date, int])` — fills zero-value months between first and last.
- **Status aggregation**: use `func.sum(case((Model.status == 'X', 1), else_=0))` — never load full objects and count in Python.
- **`_rows_to_items(rows)`**: converts `[(raw_label, count)]` query results into `[{'label': str, 'count': int}]` with deduplication and sorting.
- **`_ordered_items(items, preferred_labels)`**: reorders items to match a preferred label order (e.g., from Settings).

### Temporal semantics

All public functions accept `date_from_str` / `date_to_str` (ISO `YYYY-MM-DD` strings or `None`).  
`get_orders_data` — the marketing, for-whom, delivery-type and size breakdowns all follow the selected date range (filtered by `Order.created_at`); with no range they are all-time. One set of keys: `marketing_chart` / `marketing_total`, etc.  
`_monthly_orders_trend()` always shows last 365 days regardless of filter — it is a trend sparkline, not a filtered metric.

### Expense categorization model

```
Transaction (debit)
  └── expense_type_id (FK) → Settings (type='expense_type')
                                └── category_id (FK) → ExpenseCategory
```

Use `expense_type_id` FK — not the legacy `expense_type` string column.

---

## Omnichannel Inbox (chat)

**Status**: on branch `feature/messaging-service` (not yet merged to `main`). Code-complete for
Telegram (both variants), Viber, Instagram and WhatsApp; the Facebook-based connect flows
(Instagram OAuth, WhatsApp Embedded Signup) are untested end-to-end with a real Meta App — waiting
on the client to create it (see `tasks/2026-09-03_omnichannel-inbox-telegram.md`). No automated
tests for the Telegram-personal adapter yet (Telegram Business, Viber, Instagram, WhatsApp,
Facebook OAuth, `inbox_service` and `media_cleanup` are covered, 65 tests).

In-CRM chat where dialogs from corporate accounts land and managers reply. Page `/inbox`
(blueprint `app/blueprints/inbox/`). Config in `/settings/messaging`.

- **Channel adapters**: `app/services/messaging/adapter.py` defines `ChannelAdapter` Protocol +
  `InboundEvent` / `SentResult`. `get_adapter(channel)` resolves by `channel_type` — 5 implemented:
  - `telegram` → `telegram_business.py` — Telegram **Business API** over plain `requests`, no PTB;
    separate bot from the courier bot, token `INBOX_TELEGRAM_BOT_TOKEN`.
  - `telegram_personal` → `telegram_personal.py` (+ `telegram_personal_auth.py`,
    `telegram_personal_backfill.py`) — MTProto login (Telethon) as a real personal account, **no
    HTTP webhook**. Runs as a separate persistent process, `scripts/run_telegram_personal_worker.py`
    (one Telethon client per active channel, shared asyncio loop, pushes straight into
    `inbox_service.ingest_event` inside an app context). Session string is bearer-equivalent to
    full account access, so it's encrypted at rest via `session_crypto.py`
    (`MESSAGING_SESSION_KEY`, Fernet). History import: `flask messaging-backfill-telegram-personal
    <id> [--days]`.
  - `instagram` → `instagram_dm.py` — connected via **Facebook Login for Business** (OAuth, no
    manual token copying): manager clicks "Continue with Facebook" in `/settings/messaging`,
    picks a Page, `app/services/messaging/facebook_oauth.py` exchanges the code for a long-lived
    user token, lists Pages via `/me/accounts`, and the Page's `instagram_business_account` +
    Page Access Token become the channel (`channel.external_id` = IG-scoped id,
    `channel.fb_page_id`, `channel.fb_page_access_token_encrypted` — same Fernet pattern as
    `session_encrypted`). Sends/receives over `graph.facebook.com` (not `graph.instagram.com`)
    using the Page token. `channel.webhook_secret` is still the `hub.verify_token` for the GET
    handshake; `INBOX_INSTAGRAM_APP_SECRET` (env, App-level) verifies `X-Hub-Signature-256`.
    `register_webhook()` now does real work — `POST /{page_id}/subscribed_apps` — but the App's
    webhook **callback URL itself** is still a one-time manual paste in Meta App Dashboard by
    whoever owns the Meta App (not per-business-owner). Outbound photos go through the
    Attachment Upload API (`POST /{page_id}/message_attachments`, `is_reusable`) — no public URL
    needed, uploaded straight from the CRM with the Page token; re-encoded to JPEG first via
    `media_convert.to_jpeg_bytes` (Meta doesn't accept heic). Captions ride as a best-effort
    follow-up text message — Instagram/Messenger attachment messages can't carry inline captions.
  - `viber` → `viber.py` — Viber Bot API, token `INBOX_VIBER_BOT_TOKEN`.
  - `whatsapp` → `whatsapp.py` — connected via **Facebook Embedded Signup** (same Meta App as
    Instagram, JS-SDK popup instead of a redirect — see `messaging.html`'s `launchWhatsAppSignup`,
    config id `FACEBOOK_WHATSAPP_CONFIG_ID`, created once in the App Dashboard). The popup posts
    back `{code, waba_id, phone_number_id}`; `POST /settings/messaging/whatsapp/complete`
    (`settings/routes.py`) exchanges the code (via
    `facebook_oauth.exchange_embedded_signup_code` — no `redirect_uri`, unlike the Instagram
    exchange), registers the phone number with the Cloud API (`POST
    /{phone_number_id}/register` with a throwaway PIN — one-time, only needed again for
    re-registration), and creates the channel (`channel.external_id` = phone_number_id,
    `channel.wa_waba_id`, `channel.wa_access_token_encrypted`). 24h customer-service window
    applies (no template-message support). Outbound photos upload via `POST
    /{phone_number_id}/media` (re-encoded to JPEG via `media_convert.to_jpeg_bytes`) then send by
    `media_id` through `POST /{phone_number_id}/messages` (`image.id`, native `image.caption`).
- **Domain logic**: `inbox_service.py` (no Flask) — `ingest_event`, `send_reply`,
  `list_conversations`, `total_unread`, `ensure_media_downloaded` (lazy — webhook never downloads
  media, only stores `tg_file_id`, to avoid Telegram retry storms). `media_cleanup.py` — daily
  purge of media older than `INBOX_MEDIA_RETENTION_DAYS` (14), CLI `flask
  messaging-purge-old-media [--days]`.
- **Models**: `MessagingChannel`, `MessagingChannelAccess` (per-manager access), `Conversation`,
  `Message`. Tables `messaging_channel` / `messaging_channel_access` / `messaging_conversation` /
  `messaging_message`.
- **Webhooks** (all in `public_endpoints`, shared handler `inbox_bp._handle_webhook`):
  `POST /api/messaging/telegram/<channel_id>/webhook` (verified by
  `X-Telegram-Bot-Api-Secret-Token`); `GET|POST /api/messaging/instagram/<channel_id>/webhook` and
  `GET|POST /api/messaging/whatsapp/<channel_id>/webhook` (GET = `hub.challenge` handshake vs
  `channel.webhook_secret`; POST verified by `X-Hub-Signature-256` with the same
  `INBOX_INSTAGRAM_APP_SECRET` — one Meta App secret for both); `POST
  /api/messaging/viber/<channel_id>/webhook`. `telegram_personal` has no webhook — see worker
  above.
- **Live updates**: JS polling (`app/static/js/inbox.js`, `setTimeout` chain), no WebSocket/SSE.
- CLI: `flask messaging-set-webhook <id>` (generic `register_webhook`, Telegram/Viber/Instagram),
  `flask messaging-reconnect-instagram <id>` (checks a channel still has a stored Page token),
  `flask messaging-backfill-telegram-personal <id> [--days]`,
  `flask messaging-purge-old-media [--days]`.

## Billing & client balance (gotcha)

`client.credits` is a **denormalized running balance**, and the «Баланс клієнтів» report
derives the whole month-by-month history *backwards* from it
(`reports_service.py` → `balance = client.credits - post_paid + post_charged`). One wrong
write therefore rewrites every previously displayed month, silently. Rules:

- Never touch `client.credits` directly. Go through `billing_service.charge_delivery` /
  `reverse_delivery_charge`, or `transaction_service.apply_balance_delta` /
  `change_transaction_amount` / `delete_transaction`, all of which use
  `constants.balance_delta()` so every balance-affecting type is handled.
- A delivery is charged when its status becomes `Доставлено` and **reversed** when it
  leaves that status. The reversal is another `delivery_charge` row with a negative
  amount, dated today — so every report that sums `delivery_charge` nets out for free.
  Consequently «is this delivery charged?» is a question about the **net sum**
  (`net_charged_for_delivery`), never about a row existing.
- `Order.charged_amount` is the **frozen** price at creation/edit time; changing the
  active `PricePreset` must never re-price existing orders. Every creation path sets it,
  and edits recompute it only while the order still has uncharged deliveries.
- `delivery_charge` and `adjustment` rows are system-owned: they can't be edited or
  deleted from the transactions screen.

## Key Concepts

**Subscriptions** — a real model (`app/models/subscription.py`, table `subscription`), not an `Order` flag. `Order.delivery_type` does **not** exist; periodicity lives on `Subscription.type` (`Weekly` / `Bi-weekly` / `Monthly`) and an order belongs to a subscription via `Order.subscription_id`. On creation N orders are generated, one delivery each, where N is `Subscription.delivery_count` (1–52, default 4) — not a hardcoded 4. Requires both type + size.

**Certificates** — types: `amount` (UAH value), `size` (bouquet size), `subscription` (type + size). Auto-expire in 1 year. Status: `active` → `used` after applying to an order. Deleting the order releases the certificate back to `active`.

**Order sizes** — `S`, `M`, `L`, `XL`, `XXL`, `Власний` (requires `custom_amount`). The real list is editable in Settings (`Settings(type='size')`), so never validate a size against a hardcoded set.

**Statuses and types** — every status/type string (delivery status, transaction type, subscription status, route status, payment type…) is declared once in `app/constants.py`. Never write the literal. `Transaction.transaction_type` has **five** values — `credit`, `debit`, `delivery_charge`, `transfer`, `adjustment` — and which of them move `client.credits` is `BALANCE_SIGN_BY_TXN_TYPE` / `balance_delta()`; go through those rather than branching on the type by hand. There are no DB-level CHECK constraints yet: run `flask audit-enum-values` against a real database first to confirm nothing legacy is stored, otherwise the constraint migration will fail on deploy.

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

**Migration commit rule**: Never apply a migration (`flask db upgrade`) on any environment before the file is committed to git. The correct order is always: create file → `git commit` → `flask db upgrade`. Stubs are forbidden — if a migration was applied outside of git, add the real file to git immediately.

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
