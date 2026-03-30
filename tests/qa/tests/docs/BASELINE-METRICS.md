# Baseline Metrics - CRM Kvitkova Povnya

**Date**: 2026-03-29
**Purpose**: Pre-QA snapshot for comparison during testing

---

## 1. Test Coverage (Current State)

### Unit Tests
- **Total Tests**: 0
- **Passing**: 0 (0%)
- **Failing**: 0
- **Coverage**: 0% — no test suite exists

### Integration Tests
- **Total Tests**: 0
- **Status**: Not Implemented

### E2E Tests
- **Total Tests**: 0
- **Browsers Covered**: None

---

## 2. Known Issues (Pre-QA)

### Critical Issues
- [ ] CRITICAL-001: Zero test coverage — all features are untested

### Technical Debt
- [ ] DEBT-001: No conftest.py or pytest setup
- [ ] DEBT-002: No test fixtures / factories for models
- [ ] DEBT-003: No CI/CD pipeline for automated tests

---

## 3. Security Status

### OWASP Top 10 Coverage
- [ ] A01: Broken Access Control — login_required applied globally; florist restriction in before_request
- [ ] A02: Cryptographic Failures — password hashing used (Flask-Login); session secrets in env
- [ ] A03: Injection — SQLAlchemy ORM used (parameterized); no raw SQL observed
- [ ] A04: Insecure Design — no rate limiting observed on auth endpoints
- [ ] A05: Security Misconfiguration — debug mode in dev config; verbose errors possible
- [ ] A06: Vulnerable Components — not assessed
- [ ] A07: Authentication Failures — CSRF protection status unclear
- [ ] A08: Data Integrity Failures — no input validation layer observed
- [ ] A09: Logging Failures — no security event logging observed
- [ ] A10: SSRF — route optimizer calls external URL from env var

**Current Coverage**: 0/10 (0%) — not tested yet

---

## 4. Performance Metrics

- **Page Load Time**: Not measured
- **API Response Time**: Not measured
- **Database Query Time**: Not measured

---

## 5. Code Quality

- **Linting Errors**: Not assessed
- **Test Coverage**: 0%
- **Cyclomatic Complexity**: High (subscription_service.py — complex date calculation)

---

## 6. Predicted Issues

**PREDICTED-001**: Subscription monthly date calculation edge case
- **Predicted Severity**: P1
- **Root Cause**: Monthly logic uses "snap to weekday" — boundary conditions at month-end may miscalculate
- **Test Case**: TC-SUB-006, TC-SUB-007 will verify
- **Mitigation**: Add unit test coverage for all 3 subscription types

**PREDICTED-002**: Reschedule threshold validation missing
- **Predicted Severity**: P1
- **Root Cause**: No server-side guard if rescheduling puts deliveries below minimum gap
- **Test Case**: TC-SUB-012 will verify
- **Mitigation**: Add validation in subscription_service.apply_reschedule_plan()

**PREDICTED-003**: Role bypass on AJAX endpoints
- **Predicted Severity**: P0
- **Root Cause**: Florist restriction is in before_request but JSON endpoints may be reachable directly
- **Test Case**: TC-SEC-003, TC-SEC-004 will verify
- **Mitigation**: Add explicit role check on sensitive POST endpoints

**PREDICTED-004**: Draft subscription without contact_date accepted
- **Predicted Severity**: P2
- **Root Cause**: contact_date may not be validated server-side for draft creation
- **Test Case**: TC-SUB-016 will verify

---

**Next Steps**: Begin Week 1 testing — Authentication & Core CRUD flows first.
