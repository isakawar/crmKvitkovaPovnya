# TC-ORD: Orders Test Cases

**Category**: ORD
**Blueprint**: `app/blueprints/orders/`
**Service**: `app/services/order_service.py`
**Total Tests**: 12

---

### TC-ORD-001: Create One-Time Order

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin/manager logged in
- At least one client exists

**Test Steps**:
1. Navigate to `/orders`
2. Click "Нове замовлення"
3. Select existing client (or create new)
4. Fill in: delivery_date, size, recipient_name, recipient_phone, city, street, building_number
5. Submit

**Expected Result**:
✅ Order created with subscription_id = NULL
✅ Exactly 1 delivery created for this order
✅ Delivery status = "Очікує"
✅ Order appears in `/orders` list

**Pass/Fail Criteria**:
- ✅ PASS: Order and 1 delivery created, correct status
- ❌ FAIL: No delivery created, multiple deliveries, or DB error

---

### TC-ORD-002: Create Order for New Client (Inline Client Creation)

**Priority**: P1
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Open order creation form
2. In client field, type a new Instagram handle not in DB
3. Fill in phone number for new client
4. Complete order fields and submit

**Expected Result**:
✅ New client created automatically
✅ Order linked to new client_id
✅ Client appears in `/clients` list

**Pass/Fail Criteria**:
- ✅ PASS: Client auto-created, order linked
- ❌ FAIL: Duplicate client created, order with no client_id, or error

---

### TC-ORD-003: Order with Custom Size Requires custom_amount

**Priority**: P1
**Type**: API
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create order with size = "Власний"
2. Leave custom_amount empty
3. Submit

**Expected Result**:
✅ Validation error returned
✅ No order created

**Pass/Fail Criteria**:
- ✅ PASS: Error shown, order not saved
- ❌ FAIL: Order saved with NULL custom_amount

---

### TC-ORD-004: Update Order Details

**Priority**: P1
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- At least one order with pending delivery exists

**Test Steps**:
1. Navigate to `/orders`
2. Find and click on an order to edit
3. Change delivery_date, comment fields
4. POST to `/orders/<id>` with updated data
5. Verify changes

**Expected Result**:
✅ Order fields updated
✅ Associated delivery date also updated
✅ If date changed > 2 days for subscription order, reschedule dialog shown

**Pass/Fail Criteria**:
- ✅ PASS: Changes saved, delivery updated
- ❌ FAIL: Changes not persisted, delivery not updated

---

### TC-ORD-005: Delete Order Cascades to Delivery

**Priority**: P1
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Order with status "Очікує" delivery exists

**Test Steps**:
1. Note the order_id and its delivery_id
2. POST to `/orders/<id>/delete`
3. Check DB for orphaned delivery

**Expected Result**:
✅ Order deleted
✅ Associated delivery also deleted
✅ No orphaned delivery record

**Pass/Fail Criteria**:
- ✅ PASS: Clean cascade delete
- ❌ FAIL: Delivery remains after order deletion, or FK constraint error

---

### TC-ORD-006: Order List Filtering by Date Range

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Orders exist across multiple dates

**Test Steps**:
1. Navigate to `/orders`
2. Apply date_from = "2026-03-01", date_to = "2026-03-31"
3. Verify results

**Expected Result**:
✅ Only orders with delivery_date in March 2026 shown
✅ Orders outside range hidden

**Pass/Fail Criteria**:
- ✅ PASS: Date filter works correctly
- ❌ FAIL: Filter has no effect, or wrong date comparison

---

### TC-ORD-007: Order List Filtering by City

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Orders exist for multiple cities

**Test Steps**:
1. Navigate to `/orders`
2. Apply city filter
3. Verify only selected city's orders shown

**Expected Result**:
✅ Filter returns only orders matching selected city

**Pass/Fail Criteria**:
- ✅ PASS: Correct city filtering
- ❌ FAIL: All orders shown regardless of city

---

### TC-ORD-008: Order List Filtering by Size

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Orders of multiple sizes exist

**Test Steps**:
1. Navigate to `/orders`
2. Apply size filter = "M"
3. Verify only size-M orders shown

**Expected Result**:
✅ Only M-size orders visible

**Pass/Fail Criteria**:
- ✅ PASS: Size filter works
- ❌ FAIL: All orders shown regardless of size

---

### TC-ORD-009: Reschedule Delivery within Order

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Order linked to a subscription, pending delivery exists

**Test Steps**:
1. Find subscription order with pending delivery
2. POST to `/orders/<order_id>/delivery/<delivery_id>/reschedule`
3. Provide new delivery date
4. Check response and subsequent delivery dates

**Expected Result**:
✅ Delivery rescheduled to new date
✅ If subscription, cascade reschedule proposed for subsequent deliveries
✅ "Розподілено" deliveries reset to "Очікує" if route assigned

**Pass/Fail Criteria**:
- ✅ PASS: Reschedule applied, cascade works correctly
- ❌ FAIL: Date not updated, cascade broken, or delivered items affected

---

### TC-ORD-010: Order CSV Export

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in, orders exist

**Test Steps**:
1. Navigate to `/orders`
2. Apply date filter
3. Click export CSV
4. Download and verify CSV contents

**Expected Result**:
✅ CSV downloaded with correct columns
✅ Data matches what's shown on screen
✅ Encoding correct for Ukrainian characters

**Pass/Fail Criteria**:
- ✅ PASS: CSV exports correctly with correct data and encoding
- ❌ FAIL: Garbled characters, empty file, or missing columns

---

### TC-ORD-011: Pickup Order — No Address Required

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create order with is_pickup = True
2. Leave street/building_number empty
3. Submit

**Expected Result**:
✅ Order created without address validation error
✅ Delivery record has is_pickup = True

**Pass/Fail Criteria**:
- ✅ PASS: Pickup order created without address
- ❌ FAIL: Address validation error for pickup orders

---

### TC-ORD-012: Certificate Applied to Order

**Priority**: P1
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Active certificate exists (type: amount or size)
- Admin/manager logged in

**Test Steps**:
1. Open order creation form
2. Enter valid certificate code in certificate field
3. Verify certificate details shown (amount/size)
4. Submit order

**Expected Result**:
✅ Certificate validated successfully
✅ Order linked to certificate (order_id set on certificate)
✅ Certificate status changed to "used"
✅ used_at timestamp set

**Pass/Fail Criteria**:
- ✅ PASS: Certificate applied, status updated to "used"
- ❌ FAIL: Certificate not linked, status remains "active", or double-use allowed
