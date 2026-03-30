# TC-CLI: Clients Test Cases

**Category**: CLI
**Blueprint**: `app/blueprints/clients/`
**Service**: `app/services/client_service.py`
**Total Tests**: 10

---

### TC-CLI-001: Create New Client

**Priority**: P0
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Navigate to `/clients`
2. Click "Новий клієнт"
3. Enter instagram = "@test_client"
4. Enter phone = "+380501234567"
5. Submit form

**Expected Result**:
✅ Client created in DB
✅ Client appears in `/clients` list
✅ Created_at timestamp set automatically

**Pass/Fail Criteria**:
- ✅ PASS: Client created, appears in list
- ❌ FAIL: Error on creation, client not saved

---

### TC-CLI-002: Duplicate Instagram Detection

**Priority**: P0
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Client with instagram = "@existing_client" exists

**Test Steps**:
1. Attempt to create new client with instagram = "@existing_client"
2. Submit form

**Expected Result**:
✅ Error returned: "Клієнт з таким Instagram вже існує" (or similar)
✅ No duplicate client created

**Pass/Fail Criteria**:
- ✅ PASS: Duplicate detected, error returned
- ❌ FAIL: Duplicate client created, or unique constraint DB error shown

---

### TC-CLI-003: Duplicate Phone Detection

**Priority**: P0
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Client with phone = "+380501234567" exists

**Test Steps**:
1. Attempt to create new client with same phone number
2. Submit form

**Expected Result**:
✅ Warning or error about duplicate phone
✅ Either blocked or user prompted to confirm

**Pass/Fail Criteria**:
- ✅ PASS: Duplicate phone handled gracefully
- ❌ FAIL: Silent duplicate creation

---

### TC-CLI-004: Update Client Details

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Client exists

**Test Steps**:
1. Navigate to `/clients`
2. Click on client to edit
3. POST to `/clients/<id>` with updated phone, telegram fields
4. Verify changes saved

**Expected Result**:
✅ Client fields updated
✅ Updated values visible on client list/detail

**Pass/Fail Criteria**:
- ✅ PASS: Changes persisted
- ❌ FAIL: Changes not saved, or DB error

---

### TC-CLI-005: Delete Client Blocked by Deliveries

**Priority**: P0
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Client with associated active deliveries exists

**Test Steps**:
1. Attempt to delete a client that has deliveries
2. POST to `/clients/<id>/delete`

**Expected Result**:
✅ Deletion blocked with error: "Клієнт має доставки, видалення неможливе" (or similar)
✅ Client NOT deleted
✅ Deliveries remain intact

**Pass/Fail Criteria**:
- ✅ PASS: Block enforced, data protected
- ❌ FAIL: Client deleted with deliveries still referencing it (FK violation or orphaned data)

---

### TC-CLI-006: Search Clients by Instagram

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Multiple clients exist

**Test Steps**:
1. Navigate to `/clients`
2. Enter search query matching a client's instagram
3. Verify results

**Expected Result**:
✅ Matching client(s) shown
✅ Non-matching clients hidden

**Pass/Fail Criteria**:
- ✅ PASS: Search returns correct results
- ❌ FAIL: All clients shown regardless of search, or empty results

---

### TC-CLI-007: Search Clients by Phone

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Multiple clients exist with phone numbers

**Test Steps**:
1. Navigate to `/clients`
2. Search by partial phone number (e.g., "0501234")

**Expected Result**:
✅ Clients with matching phone number shown

**Pass/Fail Criteria**:
- ✅ PASS: Phone search works
- ❌ FAIL: Phone search not supported or returns wrong results

---

### TC-CLI-008: Filter Clients with Active Subscriptions

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Mix of clients with and without subscriptions

**Test Steps**:
1. Navigate to `/clients`
2. Apply "has_subscription" filter
3. Verify only clients with active subscriptions shown

**Expected Result**:
✅ Only subscribed clients shown
✅ Clients without subscriptions hidden

**Pass/Fail Criteria**:
- ✅ PASS: Filter works correctly
- ❌ FAIL: All clients shown regardless of subscription status

---

### TC-CLI-009: Get Client Details as JSON

**Priority**: P1
**Type**: API
**Estimated Time**: 2 minutes

**Prerequisites**:
- Client exists with ID = X

**Test Steps**:
1. Send GET request to `/clients/<X>` with `X-Requested-With: XMLHttpRequest` header
2. Verify JSON response structure

**Expected Result**:
✅ JSON response with: id, instagram, phone, telegram, credits, personal_discount
✅ HTTP 200 status

**Pass/Fail Criteria**:
- ✅ PASS: Correct JSON structure returned
- ❌ FAIL: HTML returned instead of JSON, or missing fields

---

### TC-CLI-010: Client Credits Update

**Priority**: P2
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Client exists
- Transaction created for client (credit type)

**Test Steps**:
1. Create a credit transaction for client (e.g., 100 UAH)
2. Check client's credits field in DB
3. Navigate to client detail

**Expected Result**:
✅ Client credits updated to reflect transaction
✅ Credits visible on client profile

**Pass/Fail Criteria**:
- ✅ PASS: Credits updated correctly after transaction
- ❌ FAIL: Credits not updated, or wrong amount
