# CRM Kvitkova Povnya — QA Test Suite

**Project**: CRM Kvitkova Povnya (Flask CRM for flower shop)
**QA Setup Date**: 2026-03-29
**Total Test Cases**: 89
**App URL (local)**: http://localhost:5055
**App URL (Docker)**: http://localhost:8002

---

## Test Categories

| File | Category | Tests | Description |
|------|----------|-------|-------------|
| [01-AUTH-TEST-CASES.md](01-AUTH-TEST-CASES.md) | AUTH | 10 | Login, logout, role-based access |
| [02-SUBSCRIPTION-TEST-CASES.md](02-SUBSCRIPTION-TEST-CASES.md) | SUB | 22 | Subscription CRUD, date calculations, rescheduling |
| [03-ORDERS-TEST-CASES.md](03-ORDERS-TEST-CASES.md) | ORD | 12 | One-time orders, filters, certificates |
| [04-CLIENTS-TEST-CASES.md](04-CLIENTS-TEST-CASES.md) | CLI | 10 | Client CRUD, deduplication, search |
| [05-DELIVERIES-COURIERS-TEST-CASES.md](05-DELIVERIES-COURIERS-TEST-CASES.md) | DEL | 14 | Delivery status, couriers, routes, Telegram |
| [06-CERTIFICATES-TEST-CASES.md](06-CERTIFICATES-TEST-CASES.md) | CERT | 10 | Certificate lifecycle, types, validation |
| [07-SECURITY-TEST-CASES.md](07-SECURITY-TEST-CASES.md) | SEC | 15 | OWASP Top 10, injection, access control |

---

## Priority Breakdown

| Priority | Count | Description |
|----------|-------|-------------|
| P0 | 31 | Blockers — must pass before release |
| P1 | 36 | Critical — major features |
| P2 | 17 | Important edge cases |
| P3 | 1 | Minor/cosmetic |

---

## Quick Start

### 1. Start the App

```bash
# Local dev
python run.py

# Or Docker
docker compose up
```

### 2. Seed Test Data

```bash
docker compose exec web python scripts/seed_settings.py
```

### 3. Create Test Users

Create these user types in DB for full coverage:
- Admin: `admin@test.com` / `Admin123!`
- Manager: `manager@test.com` / `Manager123!`
- Florist: `florist@test.com` / `Florist123!`

### 4. Track Progress

Update [templates/TEST-EXECUTION-TRACKING.csv](templates/TEST-EXECUTION-TRACKING.csv) after each test:
- Status: `Not Started` → `In Progress` → `Pass` or `Fail`
- Add Bug ID if failed
- Add execution date and your name

### 5. File Bugs

Use [templates/BUG-TRACKING-TEMPLATE.csv](templates/BUG-TRACKING-TEMPLATE.csv) for all failures.

---

## Quality Gates (Release Criteria)

| Gate | Target | Current |
|------|--------|---------|
| Test Execution | 100% | 0% |
| Pass Rate | >= 80% | N/A |
| P0 Bugs Open | 0 | Unknown |
| P1 Bugs Open | <= 5 | Unknown |
| Security Coverage | 9/10 OWASP | 0/10 |

---

## Known High-Risk Areas

1. **Subscription date calculation** (`subscription_service.py`) — complex monthly snap logic
2. **Reschedule cascade** — multi-delivery state machine
3. **Florist role bypass** — AJAX endpoints may lack role check
4. **Certificate double-spend** — no DB-level lock observed
5. **Draft subscription validation** — contact_date may not be enforced

See [BASELINE-METRICS.md](BASELINE-METRICS.md) for full predicted issues.

---

## Running Automated Tests (Future)

```bash
# When unit tests are added:
pytest tests/ -v

# With coverage:
pytest --cov=app tests/ --cov-report=html
```

Note: As of 2026-03-29, zero automated tests exist. All testing is currently manual.
