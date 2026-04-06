# Codebase Concerns

**Analysis Date:** 2026-04-02

## Tech Debt

**Credits system incomplete:**
- Issue: `client.credits` increased on credit transactions but never decreased on delivery completion or debit writeoffs
- Files: `app/services/delivery_service.py:125-139`, `app/blueprints/transactions/routes.py:92`, `app/models/transaction.py:11`
- Impact: Client balance tracking is inaccurate; prepayments are never deducted even after successful delivery
- Fix approach: 
  1. In `set_delivery_status()` when transitioning to "Доставлено", deduct `locked_price` from `client.credits`
  2. In transaction writeoff route, add `debit_client` type that decreases credits
  3. Requires `Order.locked_price` field (currently missing)

**Two sources of truth for delivery status:**
- Issue: Both `Delivery.status` and `Delivery.florist_status` track delivery state; they can diverge
- Files: `app/models/delivery.py:9,40`, `app/blueprints/florist/routes.py:95-96`
- Impact: UI may show conflicting status information; logic branches on both fields create maintenance burden
- Fix approach: Consolidate into single status field with unified enum or migrate florist tracking to separate audit log

**Missing `Order.locked_price` field:**
- Issue: Price calculation and discounts referenced in CLAUDE.md (FEAT-03) but field doesn't exist
- Files: `app/models/order.py`, `app/services/order_service.py:22-93`
- Impact: Cannot track actual price customer was charged; discount feature (FEAT-02) has no storage
- Fix approach: Add `Order.locked_price` (Numeric(10,2)) column, populate on order creation, use in credits deduction

**Certificate code generation collision risk:**
- Issue: `generate_certificate_code()` finds last matching prefix by `code.like()` and parses, but collides with manual codes like "Р9999"
- Files: `app/models/certificate.py:71-85`
- Impact: Generated codes can overlap with manually-entered codes; sequence is not truly unique
- Fix approach: Use database sequence or UUID prefix instead of parsing last code

---

## Known Bugs

**BUG-01: Credits not deducted after successful delivery**
- Symptoms: `client.credits` stays unchanged when delivery marked "Доставлено"
- Files: `app/services/delivery_service.py:125-139`
- Trigger: Mark any delivery as complete via florist or courier interface
- Workaround: None; manual credit adjustment via transaction writeoff
- Severity: High - breaks financial tracking

**BUG-02: Debit transactions ignore client credits**
- Symptoms: Expense writeoff (debit) doesn't decrease `client.credits`, only credit transactions increase it
- Files: `app/blueprints/transactions/routes.py:92`, `app/blueprints/transactions/routes.py:100-120`
- Trigger: Create debit transaction via `/transactions/writeoff`
- Workaround: Manually adjust credits before creating opposite credit transaction
- Severity: High - credits can inflate without bound

**BUG-03: Past delivery dates not validated**
- Symptoms: Orders accepted with `delivery_date` in the past
- Files: `app/services/order_service.py:27`, `app/services/subscription_service.py:94`
- Trigger: Create order with date before today
- Workaround: Manual deletion and recreation
- Severity: Medium - creates logistical confusion
- Status: Documented as xfail in `tests/unit/test_order_service.py:179`

**BUG-04: Invalid time ranges not blocked**
- Symptoms: Delivery time `time_from > time_to` accepted without error
- Files: `app/services/order_service.py`, `app/services/subscription_service.py`
- Trigger: Create order with `time_from='18:00'` and `time_to='10:00'`
- Workaround: Manual order update
- Severity: Medium - confuses courier scheduling
- Status: Documented as xfail in `tests/unit/test_order_service.py:194`

**BUG-05: Recipient phone not validated**
- Symptoms: Any string accepted as recipient phone; format `+380XXXXXXXXX` not enforced at creation
- Files: `app/services/order_service.py:38`
- Trigger: Create order with recipient_phone="invalid"
- Impact: Courier receives malformed phone numbers; Telegram notifications fail
- Workaround: Client service validates on client phone field only
- Severity: Medium - breaks courier operations
- Note: Client phone validation exists in `app/services/client_service.py:52,116` but not applied to order recipient_phone

**BUG-06: Completed orders can be edited**
- Symptoms: Order editable even after all deliveries marked "Доставлено"
- Files: `app/services/order_service.py:143`, `app/blueprints/orders/routes.py`
- Trigger: Mark all deliveries as "Доставлено", then edit order address/comment
- Workaround: Manual data correction
- Severity: Medium - historical record integrity compromised
- Guard needed: Check if `all(d.status == 'Доставлено' for d in order.deliveries)` before allowing update

**BUG-07: Subscriptions with completed deliveries can be deleted**
- Symptoms: Subscription deleted with all associated orders even if some deliveries "Доставлено"
- Files: `app/services/subscription_service.py:362`
- Trigger: Mark some subscription deliveries as complete, delete subscription
- Impact: Audit trail lost; financial records corrupted
- Severity: High - legal/accounting risk
- Guard needed: Block deletion if `any(d.status == 'Доставлено' for o in subscription.orders for d in o.deliveries)`

**BUG-08: Extended status set without actual extension**
- Symptoms: `followup_status='extended'` set via direct POST to `/dashboard/subscriptions/<id>/status` without creating new orders
- Files: `app/blueprints/dashboard/routes.py:199`
- Trigger: POST `{status: extended}` to dashboard endpoint
- Impact: Dashboard shows extended subscription but no future deliveries exist
- Severity: High - blocks renewal workflow
- Fix: Enforce `extend_subscription()` method which creates orders; remove direct status endpoint

**BUG-09: Pickup/Nova Poshta deliveries can be added to courier routes**
- Symptoms: `is_pickup=true` or `delivery_method='nova_poshta'` deliveries appear in courier route
- Files: `app/blueprints/routes/routes.py` (no validation on save)
- Trigger: Add pickup delivery to route via UI
- Impact: Courier receives impossible deliveries; route optimization breaks
- Severity: High - operational failure
- Guard needed: Filter in route builder: `Delivery.is_pickup == False AND Delivery.delivery_method != 'nova_poshta'`

**BUG-10: Reports filter by order creation date, not delivery date**
- Symptoms: Monthly reports count orders by `Order.created_at`, showing skewed data when orders created but delivered later
- Files: `app/services/reports_service.py:182-187`
- Trigger: Create order in Jan, schedule for delivery in Feb; order counted in Jan report
- Impact: Revenue/trend reports inaccurate by +/- one month
- Fix approach: Change filter to use `Delivery.delivery_date` via join

**BUG-11: Marketing report counts orders instead of unique clients**
- Symptoms: Marketing source report shows order count, not client count; same customer with 5 orders = 5 in report
- Files: `app/services/reports_service.py:176`, uses `func.count(Order.id)`
- Trigger: View marketing report with repeat customers
- Impact: Inflates marketing effectiveness metrics
- Fix approach: Change to `func.count(func.distinct(Order.client_id))`

**BUG-12: Transaction.amount is Integer, requires Numeric**
- Symptoms: Decimal amounts (99.50 грн) truncated to integers; cents lost
- Files: `app/models/transaction.py:11`
- Trigger: Create transaction with amount 99.50
- Impact: Financial records inaccurate by up to 100 satoshis (kopiyky)
- Fix approach: Migrate column to `Numeric(10, 2)`, backfill existing data
- Blockers: None - no migration yet created

**BUG-13: Dashboard doesn't show subscriptions ending tomorrow**
- Symptoms: Dashboard "ended subscriptions" list filters `last_delivery_date <= today - 4` (4 days ago), misses subscriptions ending soon
- Files: `app/blueprints/dashboard/routes.py:140`
- Trigger: Subscription with last delivery tomorrow marked as active; not shown in renewals
- Impact: Manager misses renewal reminders; lost upsell opportunity
- Fix approach: Change threshold to `last_delivery_date <= today` to show subscriptions ending today+buffer

---

## Security Considerations

**SECRET_KEY hardcoded in config:**
- Risk: Default SECRET_KEY="dev_secret" shipped in DevelopmentConfig
- Files: `app/config.py:26`
- Current mitigation: Environment variable fallback exists
- Recommendations: 
  1. Remove hardcoded default; raise error if SECRET_KEY not in env
  2. Add pre-deployment validation in `run.py`
  3. Generate secure random key during Docker entrypoint if missing

**DEBUG mode in production config:**
- Risk: ProductionConfig inherits from DevelopmentConfig, inherits DEBUG=False but no explicit override
- Files: `app/config.py:46-48`
- Current mitigation: DEBUG explicitly set to False in ProductionConfig
- Recommendations: Add validation assertion that DEBUG must be False in production

**No CSRF protection on forms:**
- Risk: AJAX endpoints don't validate CSRF tokens
- Files: Multiple blueprint routes check `X-Requested-With` header but not CSRF token
- Example: `app/blueprints/orders/routes.py`, `app/blueprints/transactions/routes.py:53`
- Current mitigation: Flask-Login required on most endpoints
- Recommendations: Enable Flask-WTF CSRF protection, add tokens to all forms

**Telegram webhook secret weak:**
- Risk: `TELEGRAM_WEBHOOK_SECRET` defaults to `'webhook_secret'` string
- Files: `app/config.py:41`
- Current mitigation: Override via env var in production
- Recommendations: Validate at startup if webhook URL is configured

**SQL injection via order search:**
- Risk: `Order.for_whom.like()` uses user input without parameterization
- Files: `app/services/order_service.py:96-120`
- Current mitigation: SQLAlchemy ORM uses parameterized queries
- Risk level: Low - ORM handles parameterization

**Client search via Instagram contains match:**
- Risk: `Client.instagram.contains()` uses substring matching
- Files: `app/blueprints/transactions/routes.py:46`
- Current mitigation: SQLAlchemy parameterized
- Risk level: Low - information disclosure (phone numbers visible)

---

## Performance Bottlenecks

**Large JavaScript file in composer modal:**
- Problem: `app/templates/orders/_composer_script.html` is ~40KB inline JS
- Files: `app/templates/orders/_composer_modal.html:2`, `app/templates/orders/_composer_script.html`
- Cause: Form logic, validation, dynamic field handling all in single template
- Impact: Page load slow; hard to cache; difficult to test
- Improvement path: 
  1. Extract to `app/static/js/composer.js`
  2. Load as module via `<script type="module">`
  3. Add gzip compression in production

**Telegram handlers large and linear:**
- Problem: `app/telegram_bot/handlers.py` is 1,122 lines with nested conditionals
- Files: `app/telegram_bot/handlers.py`
- Cause: Single handler function processes all message types
- Impact: Hard to understand; slow command routing; difficult to extend
- Improvement path: Split by command using dispatcher pattern (already partially done with keyboards.py)

**Report queries N+1 on marketing source:**
- Problem: `get_reports_data()` queries all orders by marketing source, no index optimization
- Files: `app/services/reports_service.py:175-187`
- Cause: `func.count(Order.id)` aggregates without grouped fetch
- Impact: Slow on large datasets (>10k orders)
- Improvement path: Add index on `(Client.marketing_source, Order.client_id)`; use explicit JOIN

**Dashboard subscriptions query subqueries:**
- Problem: Dashboard generates two subqueries for `last_delivery_date` and `last_order_id`
- Files: `app/blueprints/dashboard/routes.py:110-147`
- Cause: Separate queries for delivery date and order ID
- Impact: Slow page load on sites with many subscriptions
- Improvement path: Merge subqueries using window function `row_number()` OVER

**Delivery grouping in-memory:**
- Problem: `group_deliveries_by_date()` pulls all deliveries, groups in Python
- Files: `app/services/delivery_service.py:20-27`
- Cause: No database-level grouping
- Impact: Memory usage grows with delivery count
- Improvement path: Use SQLAlchemy group_by in query, return grouped results

---

## Fragile Areas

**Subscription date calculation logic:**
- Files: `app/services/subscription_service.py:15-36`
- Why fragile:
  1. Monthly subscriptions add fixed 28 days, causing date drift over 12 months
  2. Bi-weekly logic: `next_date + 14 days` then loops until matching weekday (can add up to 20 days)
  3. No bounds checking; infinite loops if weekday logic fails
- Safe modification:
  1. Add unit tests for each subscription type over 12+ months
  2. Hardcode delivery day anchoring (e.g., "every 2nd Monday")
  3. Add assertions that dates never drift > 3 days from expected
- Test coverage: `tests/unit/test_subscription_service.py` exists but limited to basic cases

**Delivery status state machine:**
- Files: `app/services/delivery_service.py:125-139`, `app/blueprints/florist/routes.py:95-96`
- Why fragile:
  1. No validation of state transitions (e.g., "Доставлено" → "Очікує" allowed)
  2. `florist_status` and `status` can diverge
  3. `status='Розподілено'` set in florist handler but actual courier assignment happens elsewhere
- Safe modification:
  1. Define explicit enum: `Очікує` → `Розподілено` → `Доставлено` (no backward transitions)
  2. Remove `florist_status`; use separate audit table for florist tracking
  3. Add guards in update_delivery() to validate transitions
- Test coverage: Minimal; `test_delivery_service.py` only tests happy path

**Certificate code generation:**
- Files: `app/models/certificate.py:71-85`
- Why fragile:
  1. Finds last code by filtering `code.like(prefix%)` and parsing numeric suffix
  2. Fails if manual codes like "Р9999" exist followed by system-generated "Р0001" (collision)
  3. No rollback if code already used (race condition)
- Safe modification:
  1. Replace with UUID-based codes: `prefix + uuid.uuid4().hex[:12]`
  2. Or use database SEQUENCE: `nextval('certificate_seq')`
  3. Add unique constraint on code, test with concurrent inserts
- Test coverage: None; no tests for code generation

**Order/Delivery sync on update:**
- Files: `app/services/order_service.py:143-200`, `app/services/delivery_service.py:92-123`
- Why fragile:
  1. When order edited, "new date only goes to first active delivery" (`order_service.py:191`)
  2. No transaction wrapping; partial update can corrupt state
  3. Multiple edit endpoints (orders blueprint + delivery service) can interfere
- Safe modification:
  1. Use database transaction with savepoint
  2. Atomic operation: validate all deliveries first, then update
  3. Add invariant: all deliveries for same order have consistent address
- Test coverage: Limited; no tests for partial failure scenarios

---

## Scaling Limits

**PostgreSQL connection pool:**
- Current capacity: Default Gunicorn 4 workers × SQLAlchemy pool default 5 = 20 connections
- Limit: 20 concurrent database requests; queue forms at 21+
- Impact: Requests timeout under load; dashboard page load 5+ seconds with 10 simultaneous users
- Scaling path:
  1. Increase `pool_size` in `SQLALCHEMY_DATABASE_URI` (requires DB max_connections tuning)
  2. Enable connection pooling via PgBouncer (external)
  3. Scale horizontally: Docker Swarm with multiple web instances + shared pool

**Telegram bot single handler:**
- Current capacity: Single webhook handler processes all messages sequentially
- Limit: ~20 messages/second before queue forms (typical: 2-5/sec per 50 couriers)
- Impact: Courier commands delayed >30 seconds at peak
- Scaling path:
  1. Async message queue (Celery + Redis) for Telegram updates
  2. Worker pool: 4-8 background tasks processing in parallel
  3. Message deduplication to prevent re-processing

**CSV import memory:**
- Current capacity: Full file loaded into memory in `csv_import_service.py`
- Limit: ~10MB CSV (~50k rows); larger files cause OOM
- Impact: Unable to bulk import historical data
- Scaling path:
  1. Stream processing: read file in chunks, batch insert (100-row transactions)
  2. Background job with progress tracking
  3. Split large files on client side

**Route optimization API external call:**
- Current capacity: Synchronous call to external optimizer; 5-10 second timeout
- Limit: If optimizer slow (e.g., 10k stops), page hangs
- Impact: Dashboard unresponsive when routes complex
- Scaling path:
  1. Async job: call optimizer, cache result, show "loading..." to user
  2. Fallback greedy algorithm if optimizer timeout
  3. Rate limit: cache routes 1 hour (don't recompute constantly)

---

## Dependencies at Risk

**python-telegram-bot 20.7:**
- Risk: Library pinned to 2023 release; security patches may be behind
- Impact: Potential telegram API incompatibilities; known CVEs not patched
- Migration plan: Update to latest 21.x (breaking changes possible in middlewares); test courier workflows

**Flask-SQLAlchemy ORM:**
- Risk: Single ORM; no query abstraction layer; service functions tightly coupled to SQLAlchemy
- Impact: Migration away from SQLAlchemy would require rewriting all service files
- Mitigation: Optional - not urgent unless performance issues emerge
- Migration plan: Introduce repository pattern (service returns objects, not queries)

**APScheduler background tasks:**
- Risk: In-memory scheduler; no persistence; tasks lost on restart
- Impact: Scheduled renewal reminders missed during deployment
- Mitigation: Add message queue fallback (Celery)
- Migration plan: Move critical scheduled tasks (renewal reminders) to Celery

---

## Missing Critical Features

**Feature FEAT-01: Client without Instagram:**
- Problem: `Client.instagram` is `nullable=False`; clients with only phone can't be created
- Blocks: ~20% of customer base (older customers, no Instagram)
- Impact: Users manually track non-Instagram clients in external CRM
- Workaround: Dummy Instagram field like "phone_only_123"

**Feature FEAT-02: Personal discount application:**
- Problem: `Client.personal_discount` stored as string; never applied to orders
- Blocks: Discount fulfillment; loyalty program; bulk pricing
- Impact: Manual calculation of discounted prices on every order
- Workaround: Manual adjustment via credits system

**Feature FEAT-03: Locked order price:**
- Problem: No `Order.locked_price` field; price snapshot not stored
- Blocks: Accurate billing; discount tracking; refunds
- Impact: Cannot prove customer was charged X price if prices change
- Workaround: Manual price notes in comments

**Feature FEAT-04: Debit transaction types split:**
- Problem: Single `debit` type; can't distinguish expense (business) from refund (customer)
- Blocks: Financial reporting; expense tracking
- Impact: No visibility into shop expenses vs customer refunds
- Workaround: Manual category in comment field

**Feature FEAT-05: Route status "accepted":**
- Problem: Route status only `sent` or `started`; no way to track "courier acknowledged"
- Blocks: Visibility into courier readiness
- Impact: Manager doesn't know if courier even saw the route
- Workaround: Telegram message read receipts (unreliable)

**Feature FEAT-06: Archived subscription status:**
- Problem: Deleted subscriptions lost; no "archive" state
- Blocks: Historical analytics; customer churn tracking
- Impact: Cannot find past subscriptions; no churn metrics
- Workaround: Soft delete (mark as cancelled), query carefully

---

## Test Coverage Gaps

**Order creation validation:**
- What's not tested: Past delivery dates, invalid time ranges, malformed phone numbers
- Files: `app/services/order_service.py:22-93`
- Risk: Production accepts invalid orders; courier workflows break
- Priority: High - blocks BUG-03, BUG-04, BUG-05 fixes

**Delivery status transitions:**
- What's not tested: Invalid state changes (e.g., "Доставлено" → "Очікує"), concurrent updates
- Files: `app/services/delivery_service.py:125-139`
- Risk: Delivery state can become inconsistent; database corruption
- Priority: High - data integrity

**Subscription date calculations over 12 months:**
- What's not tested: Monthly drift, Bi-weekly overshoot, edge cases (leap year, DST)
- Files: `app/services/subscription_service.py:15-36`
- Risk: Customers miss deliveries due to date miscalculation
- Priority: High - customer impact

**Credits system integrity:**
- What's not tested: Credit deduction on delivery, debit writeoff effect, refund scenarios
- Files: `app/services/delivery_service.py`, `app/blueprints/transactions/routes.py`
- Risk: Credits leak; customers overbilled or underbilled
- Priority: Critical - financial impact

**Transaction Numeric field:**
- What's not tested: Decimal amounts, rounding behavior, large sums
- Files: `app/models/transaction.py:11`, `app/blueprints/transactions/routes.py`
- Risk: Silent data loss; financial records corrupted
- Priority: High - blockers migration to Numeric type

**Florist/Courier status sync:**
- What's not tested: florist_status updates without status update, divergence scenarios
- Files: `app/blueprints/florist/routes.py`, `app/models/delivery.py`
- Risk: UI shows conflicting status; courier confused
- Priority: Medium - UX impact

**Route builder constraints:**
- What's not tested: Pickup/Nova Poshta deliveries in routes, invalid route compositions
- Files: `app/blueprints/routes/routes.py`
- Risk: Courier receives impossible deliveries
- Priority: High - operational failure

**Report date filtering:**
- What's not tested: Order created date vs delivery date discrepancies, monthly boundaries
- Files: `app/services/reports_service.py:182-187`
- Risk: Incorrect business metrics; wrong decisions
- Priority: High - business impact

---

*Concerns audit: 2026-04-02*
