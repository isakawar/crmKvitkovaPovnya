# TC-SUB: Subscription Test Cases

**Category**: SUB
**Blueprint**: `app/blueprints/subscriptions/`
**Service**: `app/services/subscription_service.py`
**Model**: `app/models/subscription.py`
**Total Tests**: 22

---

### TC-SUB-001: Create Weekly Subscription

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin/manager logged in
- At least one client exists (or can be created in form)
- Delivery settings seeded (cities, sizes, delivery types)

**Test Steps**:
1. Navigate to `/subscriptions`
2. Click "Нова підписка" (or open composer modal)
3. Select delivery_type = "Weekly"
4. Select size = "M"
5. Select delivery_day = "ПН" (Monday)
6. Enter valid recipient name, phone
7. Select city, enter street address
8. Set time_from / time_to
9. Submit form

**Expected Result**:
✅ Subscription created with status = "active"
✅ Exactly 4 orders created with subscription_id set
✅ Exactly 4 deliveries created with status = "Очікує"
✅ All 4 delivery dates fall on Monday (if delivery_day = ПН)
✅ Gap between consecutive deliveries is exactly 7 days

**Pass/Fail Criteria**:
- ✅ PASS: 4 deliveries on correct weekday, 7 days apart
- ❌ FAIL: Wrong count, wrong weekday, wrong gap

---

### TC-SUB-002: Create Bi-Weekly Subscription

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin/manager logged in, client exists

**Test Steps**:
1. Create subscription with delivery_type = "Bi-weekly"
2. Select size = "L"
3. Select delivery_day = "СР" (Wednesday)
4. Submit form

**Expected Result**:
✅ 4 orders and 4 deliveries created
✅ All delivery dates fall on Wednesday
✅ Gap between consecutive deliveries is exactly 14 days

**Pass/Fail Criteria**:
- ✅ PASS: 4 deliveries on correct weekday, 14 days apart
- ❌ FAIL: Wrong count, wrong weekday, or wrong gap (e.g., 7 days)

---

### TC-SUB-003: Create Monthly Subscription

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Admin/manager logged in, client exists

**Test Steps**:
1. Create subscription with delivery_type = "Monthly"
2. Select size = "S"
3. Select delivery_day = "ПТ" (Friday)
4. Submit form

**Expected Result**:
✅ 4 orders and 4 deliveries created
✅ All delivery dates fall on Friday
✅ Gap between consecutive deliveries is approximately 28 days (±3 days for weekday snap)

**Pass/Fail Criteria**:
- ✅ PASS: 4 deliveries on Friday, ~28 days apart
- ❌ FAIL: Wrong weekday, or gap less than 25 days or more than 31 days

**Potential Bugs to Watch For**:
- Monthly at end-of-month may produce incorrect snap (e.g., Jan 30 → Feb 28 snap skips to March)

---

### TC-SUB-004: Subscription Requires Both Type and Size

**Priority**: P0
**Type**: API
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Attempt to submit subscription form without selecting size
2. Attempt to submit without selecting delivery_type
3. Check server response

**Expected Result**:
✅ Server returns validation error (400) or form error message
✅ No subscription or orders created in DB

**Pass/Fail Criteria**:
- ✅ PASS: Validation error returned, nothing saved
- ❌ FAIL: Subscription created with NULL type or size

---

### TC-SUB-005: Subscription Size "Custom" Requires custom_amount

**Priority**: P1
**Type**: API
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Create subscription with size = "Власний"
2. Leave custom_amount empty
3. Submit

**Expected Result**:
✅ Validation error: "custom_amount required for Власний size"
✅ No subscription created

**Pass/Fail Criteria**:
- ✅ PASS: Error shown, subscription not saved
- ❌ FAIL: Subscription saved with NULL custom_amount

---

### TC-SUB-006: Weekly Date Calculation — Start of Week Boundary

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- Access to service layer or test environment

**Test Steps**:
1. Create Weekly subscription with delivery_day = "НД" (Sunday)
2. Set first delivery date to a Sunday (e.g., 2026-03-29)
3. Check all 4 generated delivery dates

**Expected Result**:
✅ Dates: 2026-03-29, 2026-04-05, 2026-04-12, 2026-04-19 (all Sundays, 7 days apart)
✅ No date falls on a different weekday

**Pass/Fail Criteria**:
- ✅ PASS: All 4 dates are Sunday, 7 days apart
- ❌ FAIL: Any date on wrong weekday or wrong interval

---

### TC-SUB-007: Monthly Date Calculation — Month-End Boundary

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- Access to subscription_service.calculate_next_delivery_date()

**Test Steps**:
1. Set first delivery date = 2026-01-30 (Friday)
2. Calculate next monthly delivery date (delivery_day = Friday)
3. Check: 2026-01-30 + 28 days = 2026-02-27 → snap to nearest Friday
4. Verify result is a valid Friday in Feb 2026

**Expected Result**:
✅ Second delivery = 2026-02-27 (Friday — exact match)
✅ Third delivery = 2026-03-27 (Friday)
✅ No delivery on Feb 29 (non-existent in non-leap year)

**Pass/Fail Criteria**:
- ✅ PASS: All dates are valid Fridays, ~28 days apart
- ❌ FAIL: Invalid date (Feb 30), wrong weekday, or skipped month

---

### TC-SUB-008: View Subscription Details

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- At least one active subscription exists

**Test Steps**:
1. Navigate to `/subscriptions`
2. Click on a subscription row to open details
3. Verify all deliveries displayed

**Expected Result**:
✅ Subscription detail modal/panel shows all 4 deliveries
✅ Each delivery shows: date, status, recipient, address
✅ JSON API `/subscriptions/<id>` returns correct structure

**Pass/Fail Criteria**:
- ✅ PASS: All delivery data displayed correctly
- ❌ FAIL: Empty deliveries, missing fields, or 404

---

### TC-SUB-009: Extend Active Subscription

**Priority**: P0
**Type**: E2E
**Estimated Time**: 5 minutes

**Prerequisites**:
- Subscription with all 4 deliveries in "Доставлено" or nearly complete status

**Test Steps**:
1. Navigate to subscription detail
2. Click "Продовжити підписку" (Extend)
3. Confirm extension

**Expected Result**:
✅ New cycle of 4 orders created (sequence_number continues)
✅ `is_extended = True` set on subscription
✅ New 4 deliveries created with "Очікує" status
✅ Dates continue from last delivery date using same interval/weekday

**Pass/Fail Criteria**:
- ✅ PASS: 4 new deliveries created, dates follow pattern
- ❌ FAIL: Extension fails, wrong delivery count, or dates don't follow pattern

---

### TC-SUB-010: Delete Subscription

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Subscription exists without "Доставлено" deliveries (or system allows deletion)

**Test Steps**:
1. Find a subscription in the list
2. Click "Видалити"
3. Confirm deletion

**Expected Result**:
✅ Subscription removed from list
✅ All associated orders and deliveries also deleted (cascade)
✅ No orphaned records in `order` or `delivery` tables

**Pass/Fail Criteria**:
- ✅ PASS: Clean cascade delete, no orphaned records
- ❌ FAIL: Subscription deleted but orders/deliveries remain, or FK constraint error

---

### TC-SUB-011: Filter Subscriptions by City

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Subscriptions exist in multiple cities

**Test Steps**:
1. Navigate to `/subscriptions`
2. Apply city filter (e.g., "Київ")
3. Verify results

**Expected Result**:
✅ Only subscriptions for selected city shown
✅ Count updates to reflect filtered results
✅ Clear filter restores full list

**Pass/Fail Criteria**:
- ✅ PASS: Filter returns correct subset
- ❌ FAIL: Wrong city subscriptions shown, or filter has no effect

---

### TC-SUB-012: Reschedule Delivery — Weekly Auto-Cascade

**Priority**: P0
**Type**: E2E
**Estimated Time**: 8 minutes

**Prerequisites**:
- Active Weekly subscription with at least 2 pending deliveries remaining

**Test Steps**:
1. Navigate to subscription detail
2. Edit first pending delivery date (change by 3+ days)
3. Confirm rescheduling plan shown
4. Accept rescheduling
5. Check all subsequent pending deliveries

**Expected Result**:
✅ System shows reschedule plan for subsequent deliveries
✅ After acceptance, all pending deliveries rescheduled 7 days apart from new date
✅ Deliveries already "Доставлено" NOT changed
✅ Route assignments reset from "Розподілено" to "Очікує"

**Pass/Fail Criteria**:
- ✅ PASS: Correct cascade rescheduling, no delivered deliveries touched
- ❌ FAIL: Subsequent deliveries not updated, delivered deliveries changed, or wrong interval

---

### TC-SUB-013: Reschedule — Bi-Weekly Minimum Gap Enforcement

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- Active Bi-weekly subscription

**Test Steps**:
1. Edit pending delivery date — move it within 9 days of the next pending delivery
2. Check system response (threshold is 9 days for Bi-weekly)

**Expected Result**:
✅ System proposes reschedule of subsequent deliveries
✅ Gap maintained at 14 days from new date
✅ System does NOT create deliveries with < 9 day gap

**Pass/Fail Criteria**:
- ✅ PASS: Min gap respected, deliveries correctly spaced
- ❌ FAIL: Deliveries created within the minimum gap threshold

---

### TC-SUB-014: Create Draft Subscription

**Priority**: P1
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- Admin/manager logged in, client exists

**Test Steps**:
1. Navigate to `/subscriptions/draft` or use draft creation endpoint
2. POST to `/subscriptions/draft` with: client_id, type, size, contact_date (future date)
3. Verify in subscriptions list

**Expected Result**:
✅ Subscription created with status = "draft"
✅ NO orders or deliveries created
✅ Draft visible in subscriptions list with contact_date shown
✅ `contact_date` field populated

**Pass/Fail Criteria**:
- ✅ PASS: Draft created, no orders, contact_date set
- ❌ FAIL: Orders created for draft, or draft not distinguishable from active

---

### TC-SUB-015: Edit Draft Contact Date

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- At least one draft subscription exists

**Test Steps**:
1. Navigate to draft subscription
2. POST to `/subscriptions/<id>/draft/edit` with new contact_date
3. Verify update

**Expected Result**:
✅ `contact_date` updated successfully
✅ Subscription remains in "draft" status
✅ No orders created by this edit

**Pass/Fail Criteria**:
- ✅ PASS: contact_date updated, status unchanged, no side effects
- ❌ FAIL: Status changed, orders created, or update fails

---

### TC-SUB-016: Create Draft Without contact_date — Validation

**Priority**: P2
**Type**: API
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. POST to `/subscriptions/draft` with: client_id, type, size — but NO contact_date
2. Check response

**Expected Result**:
✅ Server returns validation error (400)
✅ No draft subscription created

**Pass/Fail Criteria**:
- ✅ PASS: Error returned, nothing saved
- ❌ FAIL: Draft created with NULL contact_date

---

### TC-SUB-017: Subscription List Pagination

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- More than 20 subscriptions exist

**Test Steps**:
1. Navigate to `/subscriptions`
2. Scroll to bottom / click next page
3. Verify different subscriptions shown on each page

**Expected Result**:
✅ Pagination controls visible
✅ Each page shows distinct subscriptions
✅ No duplicates across pages

**Pass/Fail Criteria**:
- ✅ PASS: Pagination works correctly
- ❌ FAIL: Duplicates, missing records, or pagination controls broken

---

### TC-SUB-018: Subscription with Pickup (is_pickup=True)

**Priority**: P2
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- Admin/manager logged in, client exists

**Test Steps**:
1. Create subscription with is_pickup = True
2. Leave address fields empty (street, building_number)
3. Submit

**Expected Result**:
✅ Subscription created successfully with is_pickup = True
✅ Delivery records have is_pickup = True
✅ Address fields nullable without error

**Pass/Fail Criteria**:
- ✅ PASS: Pickup subscription created without address requirement
- ❌ FAIL: Validation error on empty address for pickup orders

---

### TC-SUB-019: Subscription Nova Poshta delivery_method

**Priority**: P2
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- Admin/manager logged in, client exists

**Test Steps**:
1. Create subscription with delivery_method = "nova_poshta"
2. Submit without street address
3. Verify deliveries

**Expected Result**:
✅ Subscription created with delivery_method = "nova_poshta"
✅ Delivery records reflect nova_poshta method

**Pass/Fail Criteria**:
- ✅ PASS: Nova Poshta method saved correctly
- ❌ FAIL: Defaults to courier, or address validation error

---

### TC-SUB-020: Dashboard Subscription Followup Status Update

**Priority**: P1
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- Subscription with followup_status = "pending" on dashboard

**Test Steps**:
1. Navigate to `/dashboard`
2. Find subscription in followup section
3. POST to `/dashboard/subscriptions/<id>/status` with status = "extended"
4. Verify update

**Expected Result**:
✅ `followup_status` updated to "extended"
✅ `followup_at` timestamp set
✅ Subscription removed from pending followup list

**Pass/Fail Criteria**:
- ✅ PASS: Status updated, timestamp set
- ❌ FAIL: Status not updated, or invalid transition allowed

---

### TC-SUB-021: Subscription Filter by Type

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Subscriptions of multiple types exist (Weekly, Monthly, Bi-weekly)

**Test Steps**:
1. Navigate to `/subscriptions`
2. Apply type filter = "Monthly"
3. Verify only Monthly subscriptions shown

**Expected Result**:
✅ Only Monthly subscriptions visible
✅ Weekly and Bi-weekly hidden

**Pass/Fail Criteria**:
- ✅ PASS: Filter returns correct type
- ❌ FAIL: Other types still shown, or filter returns empty when data exists

---

### TC-SUB-022: Import Subscription with delivery_number=5 Sets Renewal Reminder

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- CSV import feature accessible
- Valid CSV file with delivery_number=5 for a subscription row

**Test Steps**:
1. Navigate to `/import/kvitkovapovnya`
2. Upload CSV with subscription row having delivery_number=5
3. Execute import
4. Check subscription in DB

**Expected Result**:
✅ 1 delivery created (not 4)
✅ `is_renewal_reminder = True` set on subscription
✅ Subscription appears in dashboard followup section

**Pass/Fail Criteria**:
- ✅ PASS: Renewal reminder flag set, single delivery created
- ❌ FAIL: 4 deliveries created, or reminder flag missing
