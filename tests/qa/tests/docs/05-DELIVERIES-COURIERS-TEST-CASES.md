# TC-DEL: Deliveries & Couriers Test Cases

**Category**: DEL
**Blueprints**: `app/blueprints/florist/`, `app/blueprints/couriers/`, `app/blueprints/routes/`
**Services**: `app/services/delivery_service.py`, `app/services/courier_service.py`
**Total Tests**: 14

---

### TC-DEL-001: Delivery Status Transition — Очікує → Доставлено

**Priority**: P0
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- Delivery with status "Очікує" exists
- Florist logged in (or admin)

**Test Steps**:
1. Navigate to `/florist`
2. Find delivery with status "Очікує"
3. Update status to "assembled" (florist_status)
4. Then update status to "handoff"
5. Then courier marks "delivered"

**Expected Result**:
✅ Status transitions correctly through: Очікує → florist assembled → handoff → Доставлено
✅ `status_changed_at` timestamp updated on each transition
✅ `delivered_at` set when status = "Доставлено"

**Pass/Fail Criteria**:
- ✅ PASS: All transitions work, timestamps set
- ❌ FAIL: Status not updated, or timestamps missing

---

### TC-DEL-002: Delivery Status Bulk Update

**Priority**: P1
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- Multiple deliveries with "Очікує" status on same date
- Florist logged in

**Test Steps**:
1. Navigate to `/florist`
2. Select multiple deliveries
3. POST to `/florist/deliveries/status` with bulk status update
4. Verify all selected deliveries updated

**Expected Result**:
✅ All selected deliveries updated to new status
✅ Unselected deliveries NOT changed

**Pass/Fail Criteria**:
- ✅ PASS: Bulk update applies only to selected deliveries
- ❌ FAIL: All deliveries updated, or none updated

---

### TC-DEL-003: Group Deliveries by Date on Dashboard

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Deliveries exist across multiple dates

**Test Steps**:
1. Navigate to `/dashboard`
2. Observe delivery groups

**Expected Result**:
✅ Deliveries grouped by delivery_date
✅ Saturday-Friday financial week grouping applied
✅ Counts per date shown correctly

**Pass/Fail Criteria**:
- ✅ PASS: Correct grouping and counts
- ❌ FAIL: All deliveries in one group, wrong grouping

---

### TC-DEL-004: Create Courier

**Priority**: P1
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Admin/manager logged in

**Test Steps**:
1. Navigate to `/settings`
2. POST to `/couriers/new` with: name = "Тест Кур'єр", phone = "+380501111111"
3. Verify courier created

**Expected Result**:
✅ Courier created with active = True
✅ Courier visible in settings page
✅ Phone unique constraint enforced

**Pass/Fail Criteria**:
- ✅ PASS: Courier created, visible in list
- ❌ FAIL: Creation fails, or phone uniqueness not enforced

---

### TC-DEL-005: Delete Courier Blocked by Active Deliveries

**Priority**: P0
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Courier with assigned active deliveries

**Test Steps**:
1. POST to `/couriers/<id>/delete` for courier with active deliveries

**Expected Result**:
✅ Deletion blocked with appropriate error
✅ Courier NOT deleted

**Pass/Fail Criteria**:
- ✅ PASS: Block enforced
- ❌ FAIL: Courier deleted, orphaned deliveries remain

---

### TC-DEL-006: Toggle Courier Active Status

**Priority**: P2
**Type**: E2E
**Estimated Time**: 2 minutes

**Prerequisites**:
- Courier exists

**Test Steps**:
1. POST to `/couriers/<id>/toggle`
2. Verify active status flipped
3. Toggle again
4. Verify active status restored

**Expected Result**:
✅ Toggle correctly flips active/inactive
✅ Inactive couriers not shown in route assignment

**Pass/Fail Criteria**:
- ✅ PASS: Toggle works bidirectionally
- ❌ FAIL: Status doesn't change, or only one direction works

---

### TC-DEL-007: Route Assignment — Assign Courier to Route

**Priority**: P1
**Type**: E2E
**Estimated Time**: 4 minutes

**Prerequisites**:
- DeliveryRoute in "draft" status exists
- Active courier exists

**Test Steps**:
1. Navigate to `/routes`
2. Select a route
3. POST to `/routes/<id>/assign` with courier_id
4. Verify route assigned

**Expected Result**:
✅ Route assigned to courier
✅ Courier_id set on route
✅ Deliveries in route get status "Розподілено"

**Pass/Fail Criteria**:
- ✅ PASS: Route and deliveries updated
- ❌ FAIL: Courier not assigned, deliveries not updated

---

### TC-DEL-008: Route Delete

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Route in "draft" status exists

**Test Steps**:
1. POST to `/routes/<id>/delete`
2. Verify route deleted
3. Check associated deliveries reset to "Очікує"

**Expected Result**:
✅ Route deleted
✅ Deliveries that were "Розподілено" reset to "Очікує"

**Pass/Fail Criteria**:
- ✅ PASS: Route deleted, deliveries reset
- ❌ FAIL: Route deleted but deliveries stuck in "Розподілено"

---

### TC-DEL-009: Delivery Status Cannot Go Backwards

**Priority**: P1
**Type**: Integration
**Estimated Time**: 3 minutes

**Prerequisites**:
- Delivery with status "Доставлено" exists

**Test Steps**:
1. Attempt to POST status update changing "Доставлено" back to "Очікує"

**Expected Result**:
✅ Update rejected or ignored
✅ Delivered status preserved

**Pass/Fail Criteria**:
- ✅ PASS: Backward transition blocked
- ❌ FAIL: Delivery reverted to "Очікує"

**Potential Bugs to Watch For**:
- No state machine enforcement in backend — may allow any status value

---

### TC-DEL-010: Florist Dashboard Date Filtering

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Florist logged in, deliveries on multiple dates exist

**Test Steps**:
1. Navigate to `/florist`
2. Apply date filter for a specific date
3. Verify only that date's deliveries shown

**Expected Result**:
✅ Only deliveries for selected date visible
✅ Delivery count matches expected

**Pass/Fail Criteria**:
- ✅ PASS: Date filter works
- ❌ FAIL: All deliveries shown regardless of date

---

### TC-DEL-011: Assign Route and Send via Telegram

**Priority**: P1
**Type**: Integration
**Estimated Time**: 5 minutes

**Prerequisites**:
- Active courier with telegram_chat_id set
- Route in "draft" status
- Telegram bot configured

**Test Steps**:
1. POST to `/routes/<id>/assign-and-send` with courier_id
2. Check route status
3. Verify Telegram notification sent (check logs or courier receives message)

**Expected Result**:
✅ Route status updated to "sent"
✅ `sent_at` timestamp set
✅ Telegram message_id stored on route
✅ Courier receives Telegram notification

**Pass/Fail Criteria**:
- ✅ PASS: Route sent, status updated, Telegram delivered
- ❌ FAIL: Status not updated, or Telegram delivery fails silently

---

### TC-DEL-012: Route Start Time Update

**Priority**: P3
**Type**: E2E
**Estimated Time**: 2 minutes

**Prerequisites**:
- Route exists

**Test Steps**:
1. POST to `/routes/<id>/start-time` with start_time value
2. Verify route updated

**Expected Result**:
✅ `start_time` updated on route

**Pass/Fail Criteria**:
- ✅ PASS: Start time saved
- ❌ FAIL: Update fails or not persisted

---

### TC-DEL-013: Courier Edit Details

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Courier exists

**Test Steps**:
1. POST to `/couriers/<id>/edit` with updated name and phone
2. Verify changes

**Expected Result**:
✅ Courier name and phone updated
✅ Phone uniqueness still enforced (can't use another courier's phone)

**Pass/Fail Criteria**:
- ✅ PASS: Update works, uniqueness enforced
- ❌ FAIL: Update fails, or phone uniqueness bypassed

---

### TC-DEL-014: Courier Reset Telegram Binding

**Priority**: P2
**Type**: E2E
**Estimated Time**: 3 minutes

**Prerequisites**:
- Courier with telegram_chat_id set

**Test Steps**:
1. POST to `/couriers/<id>/reset-telegram`
2. Check courier's telegram fields

**Expected Result**:
✅ `telegram_chat_id` cleared (NULL)
✅ `telegram_registered = False`
✅ Courier can re-register via Telegram bot

**Pass/Fail Criteria**:
- ✅ PASS: Telegram binding cleared
- ❌ FAIL: Fields not cleared, courier blocked from re-registering
