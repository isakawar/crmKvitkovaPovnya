# TC-AUTH: Authentication & Authorization Test Cases

**Category**: AUTH
**Blueprint**: `app/blueprints/auth/`
**Total Tests**: 10

---

### TC-AUTH-001: Successful Login as Admin

**Priority**: P0
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- App running at http://localhost:5055 (or 8002 in Docker)
- Admin user exists in DB (e.g., email: admin@test.com, password: admin123)

**Test Steps**:
1. Navigate to `/login`
2. Enter valid admin email and password
3. Click "Увійти"
4. Observe redirect destination

**Expected Result**:
✅ Redirects to `/dashboard` (or `/orders`)
✅ Sidebar visible with all navigation items
✅ No "403 Forbidden" or "Unauthorized" errors

**Pass/Fail Criteria**:
- ✅ PASS: Dashboard rendered, full navigation available
- ❌ FAIL: Error message, redirect to login, or partial UI

---

### TC-AUTH-002: Login with Invalid Credentials

**Priority**: P0
**Type**: E2E
**Estimated Time**: 2 minutes

**Prerequisites**:
- App running

**Test Steps**:
1. Navigate to `/login`
2. Enter email: `nonexistent@test.com`, password: `wrongpassword`
3. Click "Увійти"

**Expected Result**:
✅ Stays on `/login` page
✅ Error message shown (e.g., "Невірний email або пароль")
✅ No session cookie set

**Pass/Fail Criteria**:
- ✅ PASS: Error shown, not logged in
- ❌ FAIL: Redirect to dashboard, no error message

---

### TC-AUTH-003: Unauthenticated Access to Protected Route

**Priority**: P0
**Type**: Security
**Estimated Time**: 2 minutes

**Prerequisites**:
- App running, no active session

**Test Steps**:
1. Without logging in, navigate directly to `/orders`
2. Observe redirect

**Expected Result**:
✅ Redirects to `/login`
✅ After login, redirects back to `/orders` (or to dashboard)

**Pass/Fail Criteria**:
- ✅ PASS: Unauthenticated access blocked, redirected to login
- ❌ FAIL: `/orders` page rendered without authentication

---

### TC-AUTH-004: Florist Role Restriction

**Priority**: P0
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- App running
- Florist user exists (user_type = 'florist')

**Test Steps**:
1. Login as florist user
2. Observe redirect after login (should go to `/florist`)
3. Navigate manually to `/orders`
4. Observe response

**Expected Result**:
✅ Login redirects to `/florist`
✅ Navigating to `/orders` returns 403 or redirects to `/florist`
✅ Florist cannot access `/clients`, `/subscriptions`, `/settings`

**Pass/Fail Criteria**:
- ✅ PASS: Florist restricted to `/florist` routes only
- ❌ FAIL: Florist can access admin/manager routes

**Potential Bugs to Watch For**:
- Direct AJAX POST calls to `/orders` from florist session
- No role check on JSON endpoints (e.g., `/clients/json`)

---

### TC-AUTH-005: Logout Clears Session

**Priority**: P1
**Type**: E2E
**Estimated Time**: 2 minutes

**Prerequisites**:
- Logged-in session active

**Test Steps**:
1. Login as any user
2. Navigate to any protected page (confirm access)
3. Click logout (navigate to `/logout`)
4. Attempt to navigate to `/orders`

**Expected Result**:
✅ Session cleared on logout
✅ `/orders` access after logout redirects to `/login`

**Pass/Fail Criteria**:
- ✅ PASS: Logout fully invalidates session
- ❌ FAIL: Protected routes still accessible after logout

---

### TC-AUTH-006: SQL Injection in Login Form

**Priority**: P0
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- App running

**Test Steps**:
1. Navigate to `/login`
2. Enter email: `admin' OR '1'='1' --`
3. Enter password: `anything`
4. Click "Увійти"

**Expected Result**:
✅ Login fails with invalid credentials message
✅ No SQL error exposed in response
✅ User NOT authenticated

**Pass/Fail Criteria**:
- ✅ PASS: Injection blocked, no data leaked
- ❌ FAIL: Login succeeds or SQL error message visible

---

### TC-AUTH-007: Empty Login Fields Validation

**Priority**: P2
**Type**: E2E
**Estimated Time**: 2 minutes

**Prerequisites**:
- App running

**Test Steps**:
1. Navigate to `/login`
2. Leave email empty, enter any password
3. Click "Увійти"
4. Repeat with email filled, password empty
5. Repeat with both empty

**Expected Result**:
✅ Form shows validation error for each empty field
✅ No server error (500) returned
✅ Page stays on `/login`

**Pass/Fail Criteria**:
- ✅ PASS: Validation messages shown, no 500 error
- ❌ FAIL: 500 error or unhandled exception

---

### TC-AUTH-008: Admin Can Access All Routes

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin user logged in

**Test Steps**:
1. Login as admin
2. Navigate to: `/clients`, `/orders`, `/subscriptions`, `/certificates`, `/couriers`, `/settings`, `/reports`, `/florist`
3. For each page, confirm HTTP 200 response

**Expected Result**:
✅ All pages return 200 and render content
✅ No "Access Denied" or redirect to login

**Pass/Fail Criteria**:
- ✅ PASS: All 8 routes accessible as admin
- ❌ FAIL: Any route returns 403/404 or redirects to login

---

### TC-AUTH-009: Manager Role Access

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- Manager user exists (user_type = 'manager')

**Test Steps**:
1. Login as manager
2. Navigate to: `/clients`, `/orders`, `/subscriptions`, `/certificates`
3. Attempt to access `/settings` (admin-only if restricted)
4. Check sidebar for available navigation items

**Expected Result**:
✅ Manager can access main CRM features
✅ Navigation consistent with manager role

**Pass/Fail Criteria**:
- ✅ PASS: Manager access matches documented role permissions
- ❌ FAIL: Manager blocked from core features or has unexpected admin access

---

### TC-AUTH-010: CSRF Protection on Login Form

**Priority**: P1
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- App running
- Ability to send raw HTTP POST requests (curl or Postman)

**Test Steps**:
1. Send POST request to `/login` without CSRF token:
   ```
   curl -X POST http://localhost:5055/login \
     -d "email=admin@test.com&password=admin123" \
     -c /tmp/cookies.txt
   ```
2. Check response

**Expected Result**:
✅ Request rejected with 400 Bad Request or CSRF error
✅ Session NOT established

**Pass/Fail Criteria**:
- ✅ PASS: CSRF protection active, request rejected
- ❌ FAIL: Login succeeds without CSRF token

**Potential Bugs to Watch For**:
- CSRF disabled in testing config but enabled in production
- Check `WTF_CSRF_ENABLED` in config.py
