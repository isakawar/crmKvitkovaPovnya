# TC-CERT: Certificates Test Cases

**Category**: CERT
**Blueprint**: `app/blueprints/certificates/`
**Model**: `app/models/certificate.py`
**Total Tests**: 10

---

### TC-CERT-001: Create Certificate — Amount Type

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Navigate to `/certificates`
2. Click "Новий сертифікат"
3. Select type = "amount", value_amount = 500
4. Add optional comment
5. Submit

**Expected Result**:
✅ Certificate created with unique code
✅ Status = "active"
✅ expires_at = created_at + 1 year
✅ Appears in certificates list

**Pass/Fail Criteria**:
- ✅ PASS: Certificate created with correct fields
- ❌ FAIL: No code generated, wrong expiry, or wrong type saved

---

### TC-CERT-002: Create Certificate — Size Type

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create certificate with type = "size", value_size = "L"
2. Submit

**Expected Result**:
✅ Certificate created with value_size = "L"
✅ value_amount = NULL (not applicable)

**Pass/Fail Criteria**:
- ✅ PASS: Correct type and value stored
- ❌ FAIL: Wrong type or missing value_size

---

### TC-CERT-003: Create Certificate — Subscription Type Requires Type + Size

**Priority**: P1
**Type**: API
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create certificate with type = "subscription"
2. Provide subscription_type and value_size
3. Test with missing value_size (no size) — expect error
4. Test complete data — expect success

**Expected Result**:
✅ Subscription certificate requires both bouquet_type and value_size
✅ Validation error if either missing

**Pass/Fail Criteria**:
- ✅ PASS: Validation enforced for subscription type
- ❌ FAIL: Certificate created with incomplete subscription data

---

### TC-CERT-004: Certificate Expiry — 1 Year from Creation

**Priority**: P1
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Certificate just created

**Test Steps**:
1. Create certificate
2. Check `expires_at` value in DB
3. Verify: expires_at = created_at + exactly 365 days

**Expected Result**:
✅ expires_at = created_at + 1 year
✅ No timezone issues in date calculation

**Pass/Fail Criteria**:
- ✅ PASS: Exactly 1 year expiry
- ❌ FAIL: Wrong expiry calculation, or NULL expires_at

---

### TC-CERT-005: Validate Active Certificate

**Priority**: P0
**Type**: API
**Estimated Time**: 3 minutes

**Prerequisites**:
- Active certificate with known code exists

**Test Steps**:
1. POST to `/certificates/validate` with valid code
2. Check response

**Expected Result**:
✅ Response: { success: true, certificate: { type, value, expires_at } }
✅ Certificate status remains "active" (validation doesn't consume it)

**Pass/Fail Criteria**:
- ✅ PASS: Validation returns correct data
- ❌ FAIL: 404, wrong data, or certificate consumed by validation

---

### TC-CERT-006: Apply Certificate to Order — Status Becomes "Used"

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Active certificate exists
- Order creation form accessible

**Test Steps**:
1. Create order and apply certificate code
2. Submit order
3. Check certificate status in `/certificates`

**Expected Result**:
✅ Certificate status changed to "used"
✅ `used_at` timestamp set
✅ `order_id` set on certificate to the new order's ID

**Pass/Fail Criteria**:
- ✅ PASS: Certificate consumed, linked to order
- ❌ FAIL: Certificate still "active" after use, or not linked to order

---

### TC-CERT-007: Cannot Reuse Used Certificate

**Priority**: P0
**Type**: Security
**Estimated Time**: 3 minutes

**Prerequisites**:
- Certificate with status = "used"

**Test Steps**:
1. Attempt to apply used certificate to a new order
2. POST to `/certificates/validate` with the used certificate code

**Expected Result**:
✅ Validation returns error: "Сертифікат вже використаний"
✅ Order rejected if used certificate applied

**Pass/Fail Criteria**:
- ✅ PASS: Reuse blocked
- ❌ FAIL: Used certificate accepted for another order

---

### TC-CERT-008: Expired Certificate Rejected

**Priority**: P1
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Certificate with expires_at in the past (manually set for testing)

**Test Steps**:
1. POST to `/certificates/validate` with expired certificate code
2. Attempt to apply to order

**Expected Result**:
✅ Validation returns error: "Сертифікат прострочений"
✅ Certificate not accepted for order

**Pass/Fail Criteria**:
- ✅ PASS: Expired certificate rejected
- ❌ FAIL: Expired certificate accepted

---

### TC-CERT-009: Generate Unique Certificate Code

**Priority**: P1
**Type**: API
**Estimated Time**: 2 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. GET `/certificates/generate-code`
2. Call 3 times
3. Verify all codes unique

**Expected Result**:
✅ Each call returns unique code
✅ Code format consistent (expected length/format)

**Pass/Fail Criteria**:
- ✅ PASS: Unique codes generated
- ❌ FAIL: Duplicate codes, or empty response

---

### TC-CERT-010: Filter Certificates by Status

**Priority**: P2
**Type**: E2E
**Estimated Time**: 2 minutes

**Prerequisites**:
- Mix of active, used, expired certificates

**Test Steps**:
1. Navigate to `/certificates`
2. Apply filter status = "active"
3. Verify only active certificates shown
4. Repeat for "used" and "expired"

**Expected Result**:
✅ Each filter returns only matching status certificates

**Pass/Fail Criteria**:
- ✅ PASS: Status filter works for all three statuses
- ❌ FAIL: Filter has no effect, or wrong certificates shown
