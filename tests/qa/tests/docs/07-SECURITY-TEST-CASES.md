# TC-SEC: Security Test Cases (OWASP Top 10)

**Category**: SEC
**Coverage Target**: 9/10 OWASP threats (90%)
**Total Tests**: 15

---

## A01: Broken Access Control

### TC-SEC-001: Direct URL Access Without Session

**Priority**: P0
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- No active session (fresh browser / incognito)

**Test Steps**:
1. Attempt to access the following URLs directly (no session):
   - `/orders`
   - `/clients`
   - `/subscriptions`
   - `/settings`
   - `/certificates`
   - `/couriers`
   - `/reports`
2. Record HTTP response for each

**Expected Result**:
✅ All URLs redirect to `/login` (302)
✅ No page content returned without authentication
✅ Redirect `next` parameter set correctly for post-login redirect

**Pass/Fail Criteria**:
- ✅ PASS: All 7 routes redirect to login
- ❌ FAIL: Any route returns 200 without authentication

---

### TC-SEC-002: Florist Cannot Access Admin Routes

**Priority**: P0
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- Florist user logged in

**Test Steps**:
1. As florist, attempt GET requests to:
   - `/orders`
   - `/clients`
   - `/subscriptions`
   - `/settings`
   - `/certificates`
   - `/reports`
2. Also attempt POST requests to:
   - `/orders` (create order)
   - `/clients/new`

**Expected Result**:
✅ All requests return 403 or redirect to `/florist`
✅ No data from other modules returned

**Pass/Fail Criteria**:
- ✅ PASS: Florist blocked from all non-florist routes
- ❌ FAIL: Florist can access any admin/manager route

---

### TC-SEC-003: IDOR — Access Another User's Resources

**Priority**: P0
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- Two test client records with IDs X and Y
- Manager account that "owns" only client X

**Test Steps**:
1. Login as manager
2. Access `/clients/<Y>` (client belonging to different context)
3. Attempt to update: POST to `/clients/<Y>` with modified data
4. Attempt to delete: POST to `/clients/<Y>/delete`

**Expected Result**:
✅ System either allows (multi-tenant not required) or restricts access based on role
✅ No unauthorized data modification
✅ At minimum: operations logged

**Note**: This CRM appears single-tenant (one shop), so cross-user isolation may not apply, but test verifies no insecure direct object reference via integer ID guessing.

**Pass/Fail Criteria**:
- ✅ PASS: Resources accessible only per documented permissions
- ❌ FAIL: Managers can modify/delete records that should be admin-only

---

### TC-SEC-004: AJAX Endpoint Role Check

**Priority**: P0
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- Florist session active

**Test Steps**:
1. As florist, send AJAX POST to:
   - `/orders` with JSON body (create order)
   - `/clients/new` with JSON body
   - `/subscriptions/draft` with JSON body
2. Include `X-Requested-With: XMLHttpRequest` header

**Expected Result**:
✅ All requests return 403 or redirect to login
✅ No data created despite valid session

**Pass/Fail Criteria**:
- ✅ PASS: Role check enforced on AJAX endpoints
- ❌ FAIL: JSON creation endpoints bypass role restriction

---

## A03: Injection

### TC-SEC-005: XSS in Client Instagram Field

**Priority**: P0
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create client with instagram = `<script>alert('XSS')</script>`
2. Navigate to `/clients` list
3. Navigate to client detail page
4. Check if script executes

**Expected Result**:
✅ Input escaped/sanitized — no script execution
✅ Text displayed as literal string or rejected
✅ No alert() popup shown

**Pass/Fail Criteria**:
- ✅ PASS: XSS prevented (Jinja2 auto-escaping active)
- ❌ FAIL: Alert fires or HTML rendered unsanitized

---

### TC-SEC-006: XSS in Order Comment Field

**Priority**: P1
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create order with comment = `<img src=x onerror="alert('XSS')">`
2. View order detail
3. Check if XSS fires

**Expected Result**:
✅ HTML entity-encoded in output: `&lt;img...&gt;`
✅ No XSS execution

**Pass/Fail Criteria**:
- ✅ PASS: HTML escaped correctly
- ❌ FAIL: Image tag rendered or onerror executes

---

### TC-SEC-007: SQL Injection in Search Fields

**Priority**: P0
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Navigate to `/clients`
2. In search field, enter: `' OR '1'='1`
3. Navigate to `/orders` search
4. Enter: `'; DROP TABLE "order"; --`
5. Check results and DB integrity

**Expected Result**:
✅ Search treated as literal string (no SQL injection)
✅ SQLAlchemy parameterized queries prevent injection
✅ `order` table still exists after test

**Pass/Fail Criteria**:
- ✅ PASS: Injection blocked, parameterized queries used
- ❌ FAIL: SQL error exposed, or unexpected query results

---

## A04: Insecure Design

### TC-SEC-008: No Rate Limiting on Login

**Priority**: P1
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- App running, access to curl or scripting

**Test Steps**:
1. Send 20 rapid POST requests to `/login` with wrong credentials:
   ```bash
   for i in {1..20}; do
     curl -s -X POST http://localhost:5055/login \
       -d "email=test@test.com&password=wrong$i"
   done
   ```
2. Check if requests blocked after threshold

**Expected Result**:
✅ Rate limiting blocks after N failed attempts
✅ IP or account lockout mechanism active

**Note**: This is a known gap (PREDICTED-003). Document finding if no rate limiting found.

**Pass/Fail Criteria**:
- ✅ PASS: Rate limiting enforced
- ❌ FAIL (P1 Bug): No rate limiting — unlimited brute force possible

---

## A05: Security Misconfiguration

### TC-SEC-009: Debug Mode Disabled in Production

**Priority**: P1
**Type**: Security
**Estimated Time**: 2 minutes

**Prerequisites**:
- Access to Docker production environment

**Test Steps**:
1. Trigger a 500 error (e.g., access invalid route)
2. Check error page content
3. In Docker env: verify `FLASK_ENV` not set to "development"

**Expected Result**:
✅ 500 error page shows generic message (not stack trace)
✅ No Python traceback visible in browser
✅ DEBUG = False in production config

**Pass/Fail Criteria**:
- ✅ PASS: Generic error pages in production
- ❌ FAIL: Stack traces visible (exposes code paths, file paths)

---

### TC-SEC-010: Secret Key Not Hardcoded

**Priority**: P0
**Type**: Security
**Estimated Time**: 2 minutes

**Prerequisites**:
- Access to codebase

**Test Steps**:
1. Check `app/config.py` for hardcoded SECRET_KEY
2. Check `.env` file for proper secret key configuration
3. Verify `SECRET_KEY` loaded from environment variable

**Expected Result**:
✅ SECRET_KEY loaded from `os.environ` or `.env` file
✅ No fallback to weak default like "dev-secret"
✅ `.env` file in `.gitignore`

**Pass/Fail Criteria**:
- ✅ PASS: Secret key from environment, not hardcoded
- ❌ FAIL: Weak or hardcoded secret key found

---

## A07: Authentication Failures

### TC-SEC-011: Session Cookie Security Flags

**Priority**: P1
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- App running, browser dev tools accessible

**Test Steps**:
1. Login to app
2. Open browser dev tools → Application → Cookies
3. Inspect session cookie flags

**Expected Result**:
✅ `HttpOnly` flag set (prevents XSS cookie theft)
✅ `Secure` flag set in production (HTTPS only)
✅ `SameSite` attribute set (CSRF protection)
✅ Session timeout configured (not indefinite)

**Pass/Fail Criteria**:
- ✅ PASS: All security flags present on session cookie
- ❌ FAIL: HttpOnly or Secure flag missing

---

### TC-SEC-012: Password Hashing — Not Stored in Plaintext

**Priority**: P0
**Type**: Security
**Estimated Time**: 2 minutes

**Prerequisites**:
- DB access (or read user model)

**Test Steps**:
1. Check `app/models/user.py` for password storage
2. Verify `password_hash` field uses werkzeug or bcrypt
3. Check: `SELECT password_hash FROM "user" LIMIT 5` in DB

**Expected Result**:
✅ Passwords stored as hashed strings (e.g., `pbkdf2:sha256:...`)
✅ No plaintext passwords in DB
✅ Hash function is bcrypt or PBKDF2 (not MD5/SHA1)

**Pass/Fail Criteria**:
- ✅ PASS: Secure password hashing used
- ❌ FAIL: Plaintext or weak hash (MD5/SHA1) found

---

## A08: Data Integrity Failures

### TC-SEC-013: Certificate Double-Spend Prevention

**Priority**: P0
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- Active certificate with known code

**Test Steps**:
1. Send two simultaneous POST requests applying same certificate to two different orders
2. Check final state of both orders and certificate

**Expected Result**:
✅ Only one order gets the certificate
✅ Certificate status = "used" linked to exactly one order_id
✅ Second request rejected with appropriate error

**Pass/Fail Criteria**:
- ✅ PASS: Race condition handled, no double-spend
- ❌ FAIL: Certificate applied to two orders simultaneously

---

## A09: Security Logging Failures

### TC-SEC-014: Failed Login Attempts Logged

**Priority**: P1
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- Access to app logs

**Test Steps**:
1. Make 5 failed login attempts
2. Check application logs

**Expected Result**:
✅ Failed attempts logged with: timestamp, IP, email attempted
✅ Log accessible to admin for audit

**Pass/Fail Criteria**:
- ✅ PASS: Security events logged
- ❌ FAIL (P1 Gap): No logging of failed authentication

---

## A10: Server-Side Request Forgery (SSRF)

### TC-SEC-015: Route Optimizer URL Injection

**Priority**: P1
**Type**: Security
**Estimated Time**: 5 minutes

**Prerequisites**:
- Route optimizer feature accessible
- Ability to intercept or modify requests

**Test Steps**:
1. Identify where `ROUTE_OPTIMIZER_URL` is used
2. Check if URL can be overridden via user input in request body
3. Attempt to inject internal URL (e.g., `http://localhost/admin`) as optimizer URL

**Expected Result**:
✅ Route optimizer URL is fixed from server config only
✅ No user input influences which external URL is called
✅ No SSRF possible via crafted requests

**Pass/Fail Criteria**:
- ✅ PASS: URL controlled by server config only, user input not used
- ❌ FAIL: User can supply arbitrary URL that server calls (SSRF)
