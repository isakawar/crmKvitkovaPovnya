# Wix → CRM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Site orders placed on the Wix store automatically arrive in the CRM as reviewable leads that an admin/manager can turn into a prefilled `Order` or `Subscription` in one click.

**Architecture:** A public webhook endpoint validated by a `metaSiteId` allowlist (Wix cannot send custom headers) stores each incoming order as a `WixLead` (idempotent on Wix's order id), matches it to an existing `Client` by phone/email, and resolves size/type via an admin-managed `WixProductMapping` table keyed by `catalogItemId`. A new "Інтеграції" section lists leads and lets admins manage mappings; the existing `/orders/new` form gains an optional `?lead_id=` prefill path and marks the lead `processed` on submit.

**Tech Stack:** Flask, Flask-SQLAlchemy, Alembic (Flask-Migrate), Jinja2 + Bootstrap (matches `orders/form.html`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-wix-integration-design.md`

## Global Constraints

- Business logic only in `app/services/` — routes and templates stay thin (per `CLAUDE.md`).
- Migration `down_revision` must be `add_promo_codes` (verified current head via `down_revision` grep across `migrations/versions/*.py`). Never run `flask db upgrade` before the migration file is committed to git.
- Table names: `wix_lead`, `wix_product_mapping` (explicit `__tablename__`, following the `Certificate`/`DeliveryRoute` explicit-tablename pattern since these aren't simple lowercase-class-name cases developers might assume).
- Reuse `normalize_phone` from `app/services/csv_import_service.py` — do not duplicate phone normalization logic.
- The webhook route must be added to the `public_endpoints` allowlist in `app/__init__.py`'s `require_login` — it receives unauthenticated traffic from Wix.
- New env var `WIX_ALLOWED_SITE_IDS` (comma-separated Wix `metaSiteId` values) — added to both `Config` and `DevelopmentConfig` in `app/config.py`, following the existing duplicated-config pattern (see `ROUTE_OPTIMIZER_URL`).

---

## File Structure

**New files:**
- `app/models/wix_lead.py` — `WixLead` model
- `app/models/wix_product_mapping.py` — `WixProductMapping` model
- `migrations/versions/add_wix_integration_tables.py` — creates both tables
- `app/services/wix_integration_service.py` — parsing, matching, lead lifecycle
- `app/blueprints/integrations/__init__.py` — blueprint registration
- `app/blueprints/integrations/routes.py` — webhook + leads list/ignore + mapping CRUD
- `app/templates/integrations/leads_list.html`
- `app/templates/integrations/product_mappings.html`
- `tests/unit/test_wix_integration_service.py`
- `tests/unit/test_wix_webhook_routes.py`
- `tests/unit/test_wix_order_prefill.py`

**Modified files:**
- `app/models/__init__.py` — register new models
- `app/config.py` — `WIX_ALLOWED_SITE_IDS`
- `app/__init__.py` — register `integrations_bp`, add webhook endpoint to `public_endpoints`
- `app/templates/layout.html` — nav links (mobile + desktop sidebar)
- `app/blueprints/orders/routes.py` — `order_form()` prefill, `order_create()` mark-processed
- `app/templates/orders/form.html` — prefill values/hidden fields

---

### Task 1: `WixLead` and `WixProductMapping` models + migration

**Files:**
- Create: `app/models/wix_lead.py`
- Create: `app/models/wix_product_mapping.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/add_wix_integration_tables.py`
- Test: `tests/unit/test_wix_integration_service.py` (model smoke-test only in this task)

**Interfaces:**
- Produces: `WixLead` columns — `id, wix_order_id, wix_order_number, raw_payload, status, received_at, contact_name, contact_phone, contact_email, city, street, postal_code, address_comment, item_name, catalog_item_id, quantity, amount, currency, payment_status, line_items_count, matched_client_id, mapping_matched, processed_order_id, processed_subscription_id, processed_at, processed_by_user_id` + relationships `matched_client, processed_order, processed_subscription, processed_by`.
- Produces: `WixProductMapping` columns — `id, catalog_item_id, wix_item_name, order_scenario, delivery_type, size, for_whom, is_active`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_integration_service.py
from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping


def test_wix_lead_and_mapping_models_roundtrip(session):
    mapping = WixProductMapping(
        catalog_item_id='977be4c1-a0f7-756d-7540-cf98f9208833',
        wix_item_name='Підписка на квіти М (4 доставки)',
        order_scenario='subscription',
        delivery_type='Monthly',
        size='M',
        for_whom='Дружина',
    )
    session.add(mapping)
    session.commit()

    lead = WixLead(
        wix_order_id='3521b3e3-cf2d-4093-9b77-b562f6f03165',
        wix_order_number='10255',
        raw_payload={'id': '3521b3e3-cf2d-4093-9b77-b562f6f03165'},
        status='new',
    )
    session.add(lead)
    session.commit()

    fetched = WixLead.query.filter_by(wix_order_id='3521b3e3-cf2d-4093-9b77-b562f6f03165').first()
    assert fetched is not None
    assert fetched.status == 'new'
    assert fetched.raw_payload == {'id': '3521b3e3-cf2d-4093-9b77-b562f6f03165'}

    fetched_mapping = WixProductMapping.query.filter_by(
        catalog_item_id='977be4c1-a0f7-756d-7540-cf98f9208833'
    ).first()
    assert fetched_mapping.size == 'M'
    assert fetched_mapping.is_active is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_integration_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.wix_lead'`

- [ ] **Step 3: Write the models**

```python
# app/models/wix_lead.py
from datetime import datetime

from app.extensions import db


class WixLead(db.Model):
    __tablename__ = 'wix_lead'

    id = db.Column(db.Integer, primary_key=True)
    wix_order_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    wix_order_number = db.Column(db.String(32), nullable=True)
    raw_payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='new')  # new | processed | ignored

    received_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    contact_name = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(32), nullable=True)
    contact_email = db.Column(db.String(256), nullable=True)

    city = db.Column(db.String(128), nullable=True)
    street = db.Column(db.String(500), nullable=True)
    postal_code = db.Column(db.String(16), nullable=True)
    address_comment = db.Column(db.Text, nullable=True)

    item_name = db.Column(db.String(255), nullable=True)
    catalog_item_id = db.Column(db.String(64), nullable=True, index=True)
    quantity = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    currency = db.Column(db.String(8), nullable=True)
    payment_status = db.Column(db.String(32), nullable=True)
    line_items_count = db.Column(db.Integer, nullable=True)

    matched_client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    mapping_matched = db.Column(db.Boolean, nullable=False, default=False)

    processed_order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    processed_subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    matched_client = db.relationship('Client', foreign_keys=[matched_client_id])
    processed_order = db.relationship('Order', foreign_keys=[processed_order_id])
    processed_subscription = db.relationship('Subscription', foreign_keys=[processed_subscription_id])
    processed_by = db.relationship('User', foreign_keys=[processed_by_user_id])
```

```python
# app/models/wix_product_mapping.py
from app.extensions import db


class WixProductMapping(db.Model):
    __tablename__ = 'wix_product_mapping'

    id = db.Column(db.Integer, primary_key=True)
    catalog_item_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    wix_item_name = db.Column(db.String(255), nullable=True)
    order_scenario = db.Column(db.String(16), nullable=False)  # order | subscription
    delivery_type = db.Column(db.String(32), nullable=True)  # Weekly | Monthly | Bi-weekly
    size = db.Column(db.String(32), nullable=False)
    for_whom = db.Column(db.String(64), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
```

Register both in `app/models/__init__.py` — add after the `SaleOption` import:

```python
from .wix_lead import WixLead
from .wix_product_mapping import WixProductMapping
```

And add `'WixLead', 'WixProductMapping'` to the `__all__` list at the end of the file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_integration_service.py -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

First confirm the current head is still `add_promo_codes`:

```bash
python3 -c "
import re, glob
revs, downs = {}, set()
for f in glob.glob('migrations/versions/*.py'):
    if '__pycache__' in f: continue
    s = open(f).read()
    m = re.search(r'^revision(?:\s*:\s*\w+)?\s*=\s*[\'\"]([^\'\"]+)[\'\"]', s, re.M)
    d = re.search(r'^down_revision(?:\s*:\s*[^=]+)?\s*=\s*(.+)', s, re.M)
    if m: revs[m.group(1)] = f
    if d:
        for part in re.findall(r'[\'\"]([^\'\"]+)[\'\"]', d.group(1)):
            downs.add(part)
print('HEADS:', set(revs) - downs)
"
```

Expected output: `HEADS: {'add_promo_codes'}`. If it differs, use the actual head as `down_revision` instead.

```python
# migrations/versions/add_wix_integration_tables.py
"""Add wix_lead and wix_product_mapping tables

Revision ID: add_wix_integration_tables
Revises: add_promo_codes
Create Date: 2026-08-24
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_wix_integration_tables'
down_revision = 'add_promo_codes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wix_product_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('catalog_item_id', sa.String(length=64), nullable=False),
        sa.Column('wix_item_name', sa.String(length=255), nullable=True),
        sa.Column('order_scenario', sa.String(length=16), nullable=False),
        sa.Column('delivery_type', sa.String(length=32), nullable=True),
        sa.Column('size', sa.String(length=32), nullable=False),
        sa.Column('for_whom', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('catalog_item_id'),
    )
    op.create_index(
        'ix_wix_product_mapping_catalog_item_id', 'wix_product_mapping', ['catalog_item_id']
    )

    op.create_table(
        'wix_lead',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wix_order_id', sa.String(length=64), nullable=False),
        sa.Column('wix_order_number', sa.String(length=32), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='new'),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=32), nullable=True),
        sa.Column('contact_email', sa.String(length=256), nullable=True),
        sa.Column('city', sa.String(length=128), nullable=True),
        sa.Column('street', sa.String(length=500), nullable=True),
        sa.Column('postal_code', sa.String(length=16), nullable=True),
        sa.Column('address_comment', sa.Text(), nullable=True),
        sa.Column('item_name', sa.String(length=255), nullable=True),
        sa.Column('catalog_item_id', sa.String(length=64), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(length=8), nullable=True),
        sa.Column('payment_status', sa.String(length=32), nullable=True),
        sa.Column('line_items_count', sa.Integer(), nullable=True),
        sa.Column('matched_client_id', sa.Integer(), nullable=True),
        sa.Column('mapping_matched', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('processed_order_id', sa.Integer(), nullable=True),
        sa.Column('processed_subscription_id', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['matched_client_id'], ['client.id']),
        sa.ForeignKeyConstraint(['processed_order_id'], ['order.id']),
        sa.ForeignKeyConstraint(['processed_subscription_id'], ['subscription.id']),
        sa.ForeignKeyConstraint(['processed_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wix_order_id'),
    )
    op.create_index('ix_wix_lead_wix_order_id', 'wix_lead', ['wix_order_id'])
    op.create_index('ix_wix_lead_catalog_item_id', 'wix_lead', ['catalog_item_id'])


def downgrade():
    op.drop_index('ix_wix_lead_catalog_item_id', table_name='wix_lead')
    op.drop_index('ix_wix_lead_wix_order_id', table_name='wix_lead')
    op.drop_table('wix_lead')
    op.drop_index('ix_wix_product_mapping_catalog_item_id', table_name='wix_product_mapping')
    op.drop_table('wix_product_mapping')
```

**Do not run `flask db upgrade` yet — commit first (per CLAUDE.md migration rule).**

- [ ] **Step 6: Commit**

```bash
git add app/models/wix_lead.py app/models/wix_product_mapping.py app/models/__init__.py \
        migrations/versions/add_wix_integration_tables.py tests/unit/test_wix_integration_service.py
git commit -m "feat: add WixLead and WixProductMapping models"
```

---

### Task 2: `parse_wix_payload`

**Files:**
- Create: `app/services/wix_integration_service.py`
- Test: `tests/unit/test_wix_integration_service.py`

**Interfaces:**
- Consumes: `app.services.csv_import_service.normalize_phone(raw: str) -> str | None`
- Produces: `parse_wix_payload(payload: dict) -> dict` with keys `wix_order_id, wix_order_number, meta_site_id, contact_name, contact_phone, contact_email, city, street, postal_code, address_comment, item_name, catalog_item_id, quantity, amount, currency, payment_status, line_items_count` — used by Tasks 3, 4, 7.

- [ ] **Step 1: Write the failing test**

Use a trimmed version of the real Wix payload from the task (top-level body is `{"data": {...}}`):

```python
# tests/unit/test_wix_integration_service.py (append)
import copy

SAMPLE_WIX_PAYLOAD = {
    "data": {
        "id": "3521b3e3-cf2d-4093-9b77-b562f6f03165",
        "orderNumber": "10255",
        "paymentStatus": "NOT_PAID",
        "currency": "UAH",
        "buyerEmail": "isakawar1@gmail.com",
        "context": {
            "metaSiteId": "2c31eac1-a4f1-4fd2-886d-361377a42a1f",
            "activationId": "696c1548-f824-409a-aba1-6e621f9e69d7",
        },
        "contact": {
            "name": {"first": "Влад", "last": "Білобров"},
            "email": "isakawar1@gmail.com",
            "phones": [
                {"e164Phone": "+380666746225", "primary": True},
                {"e164Phone": "+380661496436", "primary": False},
            ],
        },
        "lineItems": [
            {
                "quantity": 1,
                "catalogItemId": "977be4c1-a0f7-756d-7540-cf98f9208833",
                "itemName": "Підписка на квіти М (4 доставки)",
                "totalPrice": {"value": "6800.00", "currency": "UAH"},
            }
        ],
        "shippingInfo": {
            "logistics": {
                "shippingDestination": {
                    "address": {
                        "city": "Київ",
                        "addressLine": "вул. Зарічна, 1Г",
                        "postalCode": "02000",
                    },
                    "contactDetails": {
                        "firstName": "Владисла",
                        "lastName": "Білобров",
                        "phone": "+380661496436",
                    },
                }
            }
        },
        "priceSummary": {"total": {"value": "6800.00", "currency": "UAH"}},
    }
}


def test_parse_wix_payload_extracts_expected_fields():
    from app.services.wix_integration_service import parse_wix_payload

    parsed = parse_wix_payload(copy.deepcopy(SAMPLE_WIX_PAYLOAD))

    assert parsed['wix_order_id'] == '3521b3e3-cf2d-4093-9b77-b562f6f03165'
    assert parsed['wix_order_number'] == '10255'
    assert parsed['meta_site_id'] == '2c31eac1-a4f1-4fd2-886d-361377a42a1f'
    assert parsed['contact_name'] == 'Влад Білобров'
    assert parsed['contact_phone'] == '+380666746225'
    assert parsed['contact_email'] == 'isakawar1@gmail.com'
    assert parsed['city'] == 'Київ'
    assert parsed['street'] == 'вул. Зарічна, 1Г'
    assert parsed['postal_code'] == '02000'
    assert parsed['item_name'] == 'Підписка на квіти М (4 доставки)'
    assert parsed['catalog_item_id'] == '977be4c1-a0f7-756d-7540-cf98f9208833'
    assert parsed['quantity'] == 1
    assert parsed['amount'] == '6800.00'
    assert parsed['currency'] == 'UAH'
    assert parsed['payment_status'] == 'NOT_PAID'
    assert parsed['line_items_count'] == 1


def test_parse_wix_payload_falls_back_to_shipping_contact_phone():
    from app.services.wix_integration_service import parse_wix_payload

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    payload['data']['contact']['phones'] = []
    payload['data']['contact']['name'] = {}

    parsed = parse_wix_payload(payload)

    assert parsed['contact_phone'] == '+380661496436'
    assert parsed['contact_name'] == 'Владисла Білобров'


def test_parse_wix_payload_handles_missing_data_wrapper():
    from app.services.wix_integration_service import parse_wix_payload

    parsed = parse_wix_payload(copy.deepcopy(SAMPLE_WIX_PAYLOAD)['data'])
    assert parsed['wix_order_id'] == '3521b3e3-cf2d-4093-9b77-b562f6f03165'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k parse_wix_payload`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.wix_integration_service'`

- [ ] **Step 3: Write the implementation**

```python
# app/services/wix_integration_service.py
from app.services.csv_import_service import normalize_phone


def parse_wix_payload(payload: dict) -> dict:
    """Extract the fields the CRM needs from a Wix 'order placed' webhook body.

    Accepts either the raw Wix Automations body ({"data": {...}}) or the
    unwrapped order object directly, for easier testing.
    """
    if isinstance(payload, dict) and 'data' in payload:
        order_data = payload.get('data') or {}
    else:
        order_data = payload or {}

    contact = order_data.get('contact') or {}
    name = contact.get('name') or {}
    contact_name = ' '.join(p for p in [name.get('first'), name.get('last')] if p).strip() or None

    contact_phone = None
    phones = contact.get('phones') or []
    primary_phone = next((p for p in phones if p.get('primary')), None)
    phone_source = primary_phone or (phones[0] if phones else None)
    if phone_source and phone_source.get('e164Phone'):
        contact_phone = normalize_phone(phone_source['e164Phone'])

    contact_email = contact.get('email') or order_data.get('buyerEmail')

    shipping_dest = (
        (order_data.get('shippingInfo') or {}).get('logistics') or {}
    ).get('shippingDestination') or {}
    address = shipping_dest.get('address') or contact.get('address') or {}
    shipping_contact = shipping_dest.get('contactDetails') or {}

    if not contact_phone and shipping_contact.get('phone'):
        contact_phone = normalize_phone(shipping_contact['phone'])

    if not contact_name:
        contact_name = ' '.join(
            p for p in [shipping_contact.get('firstName'), shipping_contact.get('lastName')] if p
        ).strip() or None

    line_items = order_data.get('lineItems') or []
    first_item = line_items[0] if line_items else {}

    price_summary = order_data.get('priceSummary') or {}
    total = price_summary.get('total') or {}
    total_price = first_item.get('totalPrice') or {}

    return {
        'wix_order_id': order_data.get('id'),
        'wix_order_number': order_data.get('orderNumber'),
        'meta_site_id': (order_data.get('context') or {}).get('metaSiteId'),
        'contact_name': contact_name,
        'contact_phone': contact_phone,
        'contact_email': contact_email,
        'city': address.get('city'),
        'street': address.get('addressLine'),
        'postal_code': address.get('postalCode'),
        'address_comment': None,
        'item_name': first_item.get('itemName'),
        'catalog_item_id': first_item.get('catalogItemId'),
        'quantity': first_item.get('quantity'),
        'amount': total.get('value') or total_price.get('value'),
        'currency': total.get('currency') or order_data.get('currency'),
        'payment_status': order_data.get('paymentStatus'),
        'line_items_count': len(line_items),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k parse_wix_payload`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/wix_integration_service.py tests/unit/test_wix_integration_service.py
git commit -m "feat: parse Wix order-placed webhook payloads"
```

---

### Task 3: Client and product matching

**Files:**
- Modify: `app/services/wix_integration_service.py`
- Test: `tests/unit/test_wix_integration_service.py`

**Interfaces:**
- Consumes: `parsed: dict` from Task 2 (`contact_phone`, `contact_email` keys); `app.models.Client`; `app.models.wix_product_mapping.WixProductMapping`.
- Produces: `find_matching_client(parsed: dict) -> Client | None`, `find_product_mapping(catalog_item_id: str | None) -> WixProductMapping | None` — used by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_integration_service.py (append)
from app.models import Client
from app.models.wix_product_mapping import WixProductMapping


def test_find_matching_client_by_phone(session):
    from app.services.wix_integration_service import find_matching_client

    client = Client(instagram='vlad_flowers', phone='+380666746225')
    session.add(client)
    session.commit()

    found = find_matching_client({'contact_phone': '+380666746225', 'contact_email': None})
    assert found is not None
    assert found.id == client.id


def test_find_matching_client_by_email_when_phone_not_found(session):
    from app.services.wix_integration_service import find_matching_client

    client = Client(instagram='other_client', email='isakawar1@gmail.com')
    session.add(client)
    session.commit()

    found = find_matching_client({'contact_phone': '+380000000000', 'contact_email': 'isakawar1@gmail.com'})
    assert found is not None
    assert found.id == client.id


def test_find_matching_client_returns_none_when_no_match(session):
    from app.services.wix_integration_service import find_matching_client

    found = find_matching_client({'contact_phone': '+380000000000', 'contact_email': 'nobody@example.com'})
    assert found is None


def test_find_product_mapping_active_only(session):
    from app.services.wix_integration_service import find_product_mapping

    active = WixProductMapping(
        catalog_item_id='cat-1', order_scenario='order', size='M', is_active=True
    )
    inactive = WixProductMapping(
        catalog_item_id='cat-2', order_scenario='order', size='L', is_active=False
    )
    session.add_all([active, inactive])
    session.commit()

    assert find_product_mapping('cat-1').id == active.id
    assert find_product_mapping('cat-2') is None
    assert find_product_mapping(None) is None
    assert find_product_mapping('unknown') is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k "find_matching_client or find_product_mapping"`
Expected: FAIL with `ImportError: cannot import name 'find_matching_client'`

- [ ] **Step 3: Write the implementation**

```python
# app/services/wix_integration_service.py (append)
from app.models import Client
from app.models.wix_product_mapping import WixProductMapping


def find_matching_client(parsed: dict):
    phone = parsed.get('contact_phone')
    if phone:
        client = Client.query.filter_by(phone=phone).first()
        if client:
            return client
    email = parsed.get('contact_email')
    if email:
        client = Client.query.filter_by(email=email).first()
        if client:
            return client
    return None


def find_product_mapping(catalog_item_id):
    if not catalog_item_id:
        return None
    return WixProductMapping.query.filter_by(
        catalog_item_id=catalog_item_id, is_active=True
    ).first()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k "find_matching_client or find_product_mapping"`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/wix_integration_service.py tests/unit/test_wix_integration_service.py
git commit -m "feat: match Wix leads to existing clients and product mappings"
```

---

### Task 4: `create_or_update_lead` (idempotent lead creation)

**Files:**
- Modify: `app/services/wix_integration_service.py`
- Test: `tests/unit/test_wix_integration_service.py`

**Interfaces:**
- Consumes: `parse_wix_payload`, `find_matching_client`, `find_product_mapping` (Tasks 2-3); `app.extensions.db`; `app.models.wix_lead.WixLead`.
- Produces: `create_or_update_lead(payload: dict, parsed: dict) -> WixLead` — used by Task 7 (webhook route).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_integration_service.py (append)
from app.models.wix_lead import WixLead


def test_create_or_update_lead_creates_new_lead(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)

    lead = create_or_update_lead(payload, parsed)

    assert lead.id is not None
    assert lead.wix_order_id == '3521b3e3-cf2d-4093-9b77-b562f6f03165'
    assert lead.status == 'new'
    assert lead.contact_phone == '+380666746225'
    assert lead.mapping_matched is False
    assert lead.matched_client_id is None
    assert WixLead.query.count() == 1


def test_create_or_update_lead_is_idempotent_on_wix_order_id(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)

    first = create_or_update_lead(payload, parsed)
    second = create_or_update_lead(payload, parsed)

    assert first.id == second.id
    assert WixLead.query.count() == 1


def test_create_or_update_lead_does_not_overwrite_processed_lead(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)

    lead = create_or_update_lead(payload, parsed)
    lead.status = 'processed'
    session.commit()

    payload['data']['contact']['name'] = {'first': 'Changed', 'last': 'Name'}
    parsed2 = parse_wix_payload(payload)
    result = create_or_update_lead(payload, parsed2)

    assert result.id == lead.id
    assert result.status == 'processed'
    assert result.contact_name != 'Changed Name'


def test_create_or_update_lead_sets_matched_client_and_mapping(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    client = Client(instagram='vlad', phone='+380666746225')
    mapping = WixProductMapping(
        catalog_item_id='977be4c1-a0f7-756d-7540-cf98f9208833',
        order_scenario='subscription',
        delivery_type='Monthly',
        size='M',
    )
    session.add_all([client, mapping])
    session.commit()

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)
    lead = create_or_update_lead(payload, parsed)

    assert lead.matched_client_id == client.id
    assert lead.mapping_matched is True


def test_create_or_update_lead_raises_without_order_id(session):
    from app.services.wix_integration_service import create_or_update_lead
    import pytest

    with pytest.raises(ValueError):
        create_or_update_lead({}, {'wix_order_id': None})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k create_or_update_lead`
Expected: FAIL with `ImportError: cannot import name 'create_or_update_lead'`

- [ ] **Step 3: Write the implementation**

```python
# app/services/wix_integration_service.py (append)
from datetime import datetime

from app.extensions import db
from app.models.wix_lead import WixLead


def create_or_update_lead(payload: dict, parsed: dict) -> WixLead:
    wix_order_id = parsed.get('wix_order_id')
    if not wix_order_id:
        raise ValueError('Wix payload missing order id (data.id)')

    existing = WixLead.query.filter_by(wix_order_id=wix_order_id).first()
    if existing and existing.status != 'new':
        return existing

    client = find_matching_client(parsed)
    mapping = find_product_mapping(parsed.get('catalog_item_id'))

    lead = existing or WixLead(wix_order_id=wix_order_id)
    lead.wix_order_number = parsed.get('wix_order_number')
    lead.raw_payload = payload
    lead.status = 'new'
    lead.received_at = lead.received_at or datetime.utcnow()
    lead.contact_name = parsed.get('contact_name')
    lead.contact_phone = parsed.get('contact_phone')
    lead.contact_email = parsed.get('contact_email')
    lead.city = parsed.get('city')
    lead.street = parsed.get('street')
    lead.postal_code = parsed.get('postal_code')
    lead.address_comment = parsed.get('address_comment')
    lead.item_name = parsed.get('item_name')
    lead.catalog_item_id = parsed.get('catalog_item_id')
    lead.quantity = parsed.get('quantity')
    lead.amount = parsed.get('amount')
    lead.currency = parsed.get('currency')
    lead.payment_status = parsed.get('payment_status')
    lead.line_items_count = parsed.get('line_items_count')
    lead.matched_client_id = client.id if client else None
    lead.mapping_matched = mapping is not None

    db.session.add(lead)
    db.session.commit()
    return lead
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k create_or_update_lead`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/wix_integration_service.py tests/unit/test_wix_integration_service.py
git commit -m "feat: idempotent Wix lead creation"
```

---

### Task 5: `mark_lead_processed`

**Files:**
- Modify: `app/services/wix_integration_service.py`
- Test: `tests/unit/test_wix_integration_service.py`

**Interfaces:**
- Consumes: `WixLead` instance; `Order` or `Subscription` instance; a user object with `.id`.
- Produces: `mark_lead_processed(lead: WixLead, entity, user) -> None` — used by Task 13 (`order_create`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_integration_service.py (append)
from app.models.user import User
from app.models.subscription import Subscription
from app.models.order import Order
import datetime as _dt


def test_mark_lead_processed_with_order(session, client_fixture):
    from app.services.wix_integration_service import mark_lead_processed

    lead = WixLead(
        wix_order_id='order-1', raw_payload={}, status='new',
    )
    order = Order(
        client_id=client_fixture.id, recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', delivery_date=_dt.date.today(), for_whom='Дружина',
    )
    user = User(username='mgr', email='mgr@example.com', user_type='manager')
    user.set_password('x')
    session.add_all([lead, order, user])
    session.commit()

    mark_lead_processed(lead, order, user)

    assert lead.status == 'processed'
    assert lead.processed_order_id == order.id
    assert lead.processed_subscription_id is None
    assert lead.processed_by_user_id == user.id
    assert lead.processed_at is not None


def test_mark_lead_processed_with_subscription(session, subscription_fixture):
    from app.services.wix_integration_service import mark_lead_processed

    lead = WixLead(wix_order_id='order-2', raw_payload={}, status='new')
    user = User(username='mgr2', email='mgr2@example.com', user_type='admin')
    user.set_password('x')
    session.add_all([lead, user])
    session.commit()

    mark_lead_processed(lead, subscription_fixture, user)

    assert lead.status == 'processed'
    assert lead.processed_subscription_id == subscription_fixture.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k mark_lead_processed`
Expected: FAIL with `ImportError: cannot import name 'mark_lead_processed'`

- [ ] **Step 3: Write the implementation**

```python
# app/services/wix_integration_service.py (append)
from app.models.order import Order
from app.models.subscription import Subscription


def mark_lead_processed(lead: WixLead, entity, user) -> None:
    lead.status = 'processed'
    lead.processed_at = datetime.utcnow()
    lead.processed_by_user_id = getattr(user, 'id', None)

    if isinstance(entity, Subscription):
        lead.processed_subscription_id = entity.id
        lead.processed_order_id = entity.orders[0].id if entity.orders else None
    elif isinstance(entity, Order):
        lead.processed_order_id = entity.id

    db.session.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_integration_service.py -v -k mark_lead_processed`
Expected: PASS (2 tests). Then run the whole service test file to make sure nothing else broke:

Run: `pytest tests/unit/test_wix_integration_service.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/wix_integration_service.py tests/unit/test_wix_integration_service.py
git commit -m "feat: mark Wix leads processed when converted to an order/subscription"
```

---

### Task 6: `WIX_ALLOWED_SITE_IDS` config

**Files:**
- Modify: `app/config.py`

**Interfaces:**
- Produces: `current_app.config['WIX_ALLOWED_SITE_IDS']` — a comma-separated string, used by Task 7.

- [ ] **Step 1: Add the config value**

In `app/config.py`, inside `class Config:` add after the `DEPOT_ADDRESS` line (line 24):

```python
    DEPOT_ADDRESS = os.environ.get('DEPOT_ADDRESS', '')

    # Wix site order integration — comma-separated allowed data.context.metaSiteId values
    WIX_ALLOWED_SITE_IDS = os.environ.get('WIX_ALLOWED_SITE_IDS', '')
```

And inside `class DevelopmentConfig:` add after its own `DEPOT_ADDRESS` line (line 57):

```python
    DEPOT_ADDRESS = os.environ.get('DEPOT_ADDRESS', '')

    # Wix site order integration — comma-separated allowed data.context.metaSiteId values
    WIX_ALLOWED_SITE_IDS = os.environ.get('WIX_ALLOWED_SITE_IDS', '')
```

- [ ] **Step 2: Verify by import**

Run: `python3 -c "from app.config import Config, DevelopmentConfig; print(Config.WIX_ALLOWED_SITE_IDS, DevelopmentConfig.WIX_ALLOWED_SITE_IDS)"`
Expected: prints two empty strings (no `AttributeError`)

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat: add WIX_ALLOWED_SITE_IDS config for webhook validation"
```

---

### Task 7: Webhook endpoint (`integrations` blueprint, part 1)

**Files:**
- Create: `app/blueprints/integrations/__init__.py`
- Create: `app/blueprints/integrations/routes.py`
- Modify: `app/__init__.py`
- Test: `tests/unit/test_wix_webhook_routes.py`

**Interfaces:**
- Consumes: `wix_integration_service.parse_wix_payload`, `create_or_update_lead` (Tasks 2, 4).
- Produces: `integrations_bp` (Flask Blueprint, name `'integrations'`), route `POST /api/integrations/wix/order-placed` (endpoint `integrations.wix_order_webhook`) — used by Task 8's blueprint registration and by external Wix Automations config.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_webhook_routes.py
import copy
import json

from tests.unit.test_wix_integration_service import SAMPLE_WIX_PAYLOAD
from app.models.wix_lead import WixLead


def test_webhook_rejects_when_not_configured(app):
    app.config['WIX_ALLOWED_SITE_IDS'] = ''
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps(SAMPLE_WIX_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 503


def test_webhook_rejects_unknown_site(app):
    app.config['WIX_ALLOWED_SITE_IDS'] = 'some-other-site-id'
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps(SAMPLE_WIX_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 403


def test_webhook_accepts_known_site_and_creates_lead(app, session):
    app.config['WIX_ALLOWED_SITE_IDS'] = '2c31eac1-a4f1-4fd2-886d-361377a42a1f'
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps(SAMPLE_WIX_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    lead = WixLead.query.get(body['lead_id'])
    assert lead is not None
    assert lead.wix_order_id == '3521b3e3-cf2d-4093-9b77-b562f6f03165'


def test_webhook_rejects_invalid_json_body(app):
    app.config['WIX_ALLOWED_SITE_IDS'] = '2c31eac1-a4f1-4fd2-886d-361377a42a1f'
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data='not json',
        content_type='application/json',
    )
    assert resp.status_code == 400


def test_webhook_is_public_no_login_required(app):
    """The require_login before_request hook must not redirect this endpoint."""
    app.config['WIX_ALLOWED_SITE_IDS'] = 'x'
    app.config['LOGIN_DISABLED'] = False
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert resp.status_code != 302
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_webhook_routes.py -v`
Expected: FAIL with 404s (`assert 404 == 503` etc.) since the route doesn't exist yet

- [ ] **Step 3: Write the blueprint**

```python
# app/blueprints/integrations/__init__.py
from flask import Blueprint

integrations_bp = Blueprint('integrations', __name__)

from app.blueprints.integrations import routes  # noqa: F401, E402
```

```python
# app/blueprints/integrations/routes.py
import hmac

from flask import current_app, jsonify, request

from app.blueprints.integrations import integrations_bp
from app.services import wix_integration_service as wix_service


def _allowed_site_ids():
    raw = current_app.config.get('WIX_ALLOWED_SITE_IDS') or ''
    return {s.strip() for s in raw.split(',') if s.strip()}


@integrations_bp.route('/api/integrations/wix/order-placed', methods=['POST'])
def wix_order_webhook():
    allowed_ids = _allowed_site_ids()
    if not allowed_ids:
        return jsonify({'ok': False, 'error': 'integration not configured'}), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'error': 'invalid json body'}), 400

    parsed = wix_service.parse_wix_payload(payload)
    meta_site_id = parsed.get('meta_site_id')
    is_allowed = bool(meta_site_id) and any(
        hmac.compare_digest(meta_site_id, allowed) for allowed in allowed_ids
    )
    if not is_allowed:
        return jsonify({'ok': False, 'error': 'unknown site'}), 403

    try:
        lead = wix_service.create_or_update_lead(payload, parsed)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    return jsonify({'ok': True, 'lead_id': lead.id}), 200
```

Register the blueprint in `app/__init__.py`. In the imports block (after `from app.blueprints.notifications import notifications_bp`):

```python
    from app.blueprints.notifications import notifications_bp
    from app.blueprints.integrations import integrations_bp
```

In the registration block (after `app.register_blueprint(notifications_bp)`):

```python
    app.register_blueprint(notifications_bp)
    app.register_blueprint(integrations_bp)
```

In `require_login()`, add the webhook endpoint to `public_endpoints`:

```python
        public_endpoints = [
            'auth.login', 'static', 'changelog', 'settings.serve_sale_option_icon',
            'integrations.wix_order_webhook',
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_webhook_routes.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/blueprints/integrations/__init__.py app/blueprints/integrations/routes.py \
        app/__init__.py tests/unit/test_wix_webhook_routes.py
git commit -m "feat: add Wix order-placed webhook endpoint with metaSiteId auth"
```

---

### Task 8: Leads list + ignore (`integrations` blueprint, part 2)

**Files:**
- Modify: `app/blueprints/integrations/routes.py`
- Create: `app/templates/integrations/leads_list.html`
- Test: `tests/unit/test_wix_webhook_routes.py`

**Interfaces:**
- Consumes: `WixLead` model (Task 1).
- Produces: routes `GET /integrations/wix-leads` (endpoint `integrations.wix_leads_list`), `POST /integrations/wix-leads/<int:lead_id>/ignore` (endpoint `integrations.wix_lead_ignore`) — the list route is linked from Task 10's nav and links to Task 12's `/orders/new?lead_id=`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_webhook_routes.py (append)
from app.models.user import User


def _login(app, client, user):
    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user.id)
        flask_session['_fresh'] = True


def _make_manager(session):
    user = User(username='mgr', email='mgr@example.com', user_type='manager', is_active=True)
    user.set_password('secret')
    session.add(user)
    session.commit()
    return user


def test_leads_list_requires_admin_or_manager(app, session):
    florist = User(username='flo', email='flo@example.com', user_type='florist', is_active=True)
    florist.set_password('secret')
    session.add(florist)
    session.commit()

    client = app.test_client()
    _login(app, client, florist)
    resp = client.get('/integrations/wix-leads')
    assert resp.status_code == 403


def test_leads_list_shows_new_leads(app, session):
    manager = _make_manager(session)
    lead = WixLead(
        wix_order_id='o-1', wix_order_number='100', raw_payload={}, status='new',
        item_name='Підписка на квіти М (4 доставки)',
    )
    session.add(lead)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.get('/integrations/wix-leads')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Підписка на квіти М (4 доставки)' in html


def test_ignore_lead_changes_status(app, session):
    manager = _make_manager(session)
    lead = WixLead(wix_order_id='o-2', raw_payload={}, status='new')
    session.add(lead)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.post(f'/integrations/wix-leads/{lead.id}/ignore', follow_redirects=True)

    assert resp.status_code == 200
    assert WixLead.query.get(lead.id).status == 'ignored'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_webhook_routes.py -v -k "leads_list or ignore_lead"`
Expected: FAIL with 404s

- [ ] **Step 3: Write the routes and template**

Append to `app/blueprints/integrations/routes.py`:

```python
from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.wix_lead import WixLead


def _is_admin_or_manager():
    return getattr(current_user, 'user_type', None) in ('admin', 'manager')


@integrations_bp.route('/integrations/wix-leads', methods=['GET'])
@login_required
def wix_leads_list():
    if not _is_admin_or_manager():
        abort(403)
    status_filter = request.args.get('status', 'new')
    query = WixLead.query
    if status_filter in ('new', 'processed', 'ignored'):
        query = query.filter_by(status=status_filter)
    leads = query.order_by(WixLead.received_at.desc()).all()
    return render_template(
        'integrations/leads_list.html', leads=leads, status_filter=status_filter
    )


@integrations_bp.route('/integrations/wix-leads/<int:lead_id>/ignore', methods=['POST'])
@login_required
def wix_lead_ignore(lead_id):
    if not _is_admin_or_manager():
        abort(403)
    lead = WixLead.query.get_or_404(lead_id)
    lead.status = 'ignored'
    db.session.commit()
    flash('Заявку проігноровано', 'success')
    return redirect(url_for('integrations.wix_leads_list'))
```

```html
{# app/templates/integrations/leads_list.html #}
{% extends "layout.html" %}
{% block content %}
<div class="container-fluid">
    <h2 class="mb-4">Заявки з сайту</h2>

    <div class="mb-3">
        <a href="?status=new" class="btn btn-sm {% if status_filter == 'new' %}btn-primary{% else %}btn-outline-secondary{% endif %}">Нові</a>
        <a href="?status=processed" class="btn btn-sm {% if status_filter == 'processed' %}btn-primary{% else %}btn-outline-secondary{% endif %}">Оброблені</a>
        <a href="?status=ignored" class="btn btn-sm {% if status_filter == 'ignored' %}btn-primary{% else %}btn-outline-secondary{% endif %}">Ігноровані</a>
    </div>

    <table class="table table-hover align-middle">
        <thead>
            <tr>
                <th>Отримано</th>
                <th>№ замовлення</th>
                <th>Товар</th>
                <th>Сума</th>
                <th>Контакт</th>
                <th>Клієнт</th>
                <th>Мапінг</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {% for lead in leads %}
            <tr>
                <td>{{ lead.received_at | kyiv_time }}</td>
                <td>{{ lead.wix_order_number or '—' }}</td>
                <td>
                    {{ lead.item_name or '—' }}
                    {% if lead.line_items_count and lead.line_items_count > 1 %}
                        <span class="badge bg-warning text-dark">кілька позицій — перевірте вручну</span>
                    {% endif %}
                </td>
                <td>{{ lead.amount or '—' }} {{ lead.currency or '' }}</td>
                <td>{{ lead.contact_name or '—' }}<br><small class="text-muted">{{ lead.contact_phone or lead.contact_email or '' }}</small></td>
                <td>
                    {% if lead.matched_client_id %}
                        <span class="badge bg-success">знайдено</span>
                    {% else %}
                        <span class="badge bg-secondary">не знайдено</span>
                    {% endif %}
                </td>
                <td>
                    {% if lead.mapping_matched %}
                        <span class="badge bg-success">є</span>
                    {% else %}
                        <span class="badge bg-secondary">немає</span>
                    {% endif %}
                </td>
                <td>
                    {% if status_filter == 'new' %}
                    <a href="{{ url_for('orders.order_form', lead_id=lead.id) }}" class="btn btn-sm btn-primary">Обробити</a>
                    <form method="post" action="{{ url_for('integrations.wix_lead_ignore', lead_id=lead.id) }}" class="d-inline">
                        <button type="submit" class="btn btn-sm btn-outline-secondary">Ігнорувати</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% else %}
            <tr><td colspan="8" class="text-center text-muted">Немає заявок</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_webhook_routes.py -v`
Expected: all tests PASS (`assert response.status_code == 200` etc. — note `orders.order_form` referenced by `url_for` in the template doesn't need `lead_id` support yet to resolve the URL, since Flask's `url_for` just appends it as a query string)

- [ ] **Step 5: Commit**

```bash
git add app/blueprints/integrations/routes.py app/templates/integrations/leads_list.html \
        tests/unit/test_wix_webhook_routes.py
git commit -m "feat: add Wix leads list and ignore action"
```

---

### Task 9: Product mapping CRUD (`integrations` blueprint, part 3)

**Files:**
- Modify: `app/blueprints/integrations/routes.py`
- Create: `app/templates/integrations/product_mappings.html`
- Test: `tests/unit/test_wix_webhook_routes.py`

**Interfaces:**
- Consumes: `WixProductMapping` model (Task 1).
- Produces: routes `GET /integrations/wix-product-mappings` (`integrations.wix_product_mappings_list`), `POST /integrations/wix-product-mappings/new` (`integrations.wix_product_mapping_create`), `POST /integrations/wix-product-mappings/<int:mapping_id>/edit` (`integrations.wix_product_mapping_edit`), `POST /integrations/wix-product-mappings/<int:mapping_id>/delete` (`integrations.wix_product_mapping_delete`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_webhook_routes.py (append)
from app.models.wix_product_mapping import WixProductMapping


def test_create_product_mapping(app, session):
    manager = _make_manager(session)
    client = app.test_client()
    _login(app, client, manager)

    resp = client.post('/integrations/wix-product-mappings/new', data={
        'catalog_item_id': 'cat-abc',
        'wix_item_name': 'Букет S',
        'order_scenario': 'order',
        'size': 'S',
        'for_whom': 'Дружина',
    }, follow_redirects=True)

    assert resp.status_code == 200
    mapping = WixProductMapping.query.filter_by(catalog_item_id='cat-abc').first()
    assert mapping is not None
    assert mapping.size == 'S'


def test_edit_product_mapping(app, session):
    manager = _make_manager(session)
    mapping = WixProductMapping(catalog_item_id='cat-xyz', order_scenario='order', size='M')
    session.add(mapping)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.post(f'/integrations/wix-product-mappings/{mapping.id}/edit', data={
        'wix_item_name': 'Оновлена назва',
        'order_scenario': 'subscription',
        'delivery_type': 'Weekly',
        'size': 'L',
        'for_whom': '',
        'is_active': 'on',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = WixProductMapping.query.get(mapping.id)
    assert updated.order_scenario == 'subscription'
    assert updated.delivery_type == 'Weekly'
    assert updated.size == 'L'


def test_delete_product_mapping(app, session):
    manager = _make_manager(session)
    mapping = WixProductMapping(catalog_item_id='cat-del', order_scenario='order', size='M')
    session.add(mapping)
    session.commit()
    mapping_id = mapping.id

    client = app.test_client()
    _login(app, client, manager)
    resp = client.post(f'/integrations/wix-product-mappings/{mapping_id}/delete', follow_redirects=True)

    assert resp.status_code == 200
    assert WixProductMapping.query.get(mapping_id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_webhook_routes.py -v -k product_mapping`
Expected: FAIL with 404s

- [ ] **Step 3: Write the routes and template**

Append to `app/blueprints/integrations/routes.py`:

```python
from app.models.wix_product_mapping import WixProductMapping


@integrations_bp.route('/integrations/wix-product-mappings', methods=['GET'])
@login_required
def wix_product_mappings_list():
    if not _is_admin_or_manager():
        abort(403)
    mappings = WixProductMapping.query.order_by(WixProductMapping.id.desc()).all()
    return render_template('integrations/product_mappings.html', mappings=mappings)


@integrations_bp.route('/integrations/wix-product-mappings/new', methods=['POST'])
@login_required
def wix_product_mapping_create():
    if not _is_admin_or_manager():
        abort(403)
    catalog_item_id = (request.form.get('catalog_item_id') or '').strip()
    order_scenario = request.form.get('order_scenario') or ''
    size = request.form.get('size') or ''
    if not catalog_item_id or order_scenario not in ('order', 'subscription') or not size:
        flash('Заповніть catalog_item_id, сценарій і розмір', 'danger')
        return redirect(url_for('integrations.wix_product_mappings_list'))

    mapping = WixProductMapping(
        catalog_item_id=catalog_item_id,
        wix_item_name=(request.form.get('wix_item_name') or '').strip() or None,
        order_scenario=order_scenario,
        delivery_type=(request.form.get('delivery_type') or '').strip() or None,
        size=size,
        for_whom=(request.form.get('for_whom') or '').strip() or None,
    )
    db.session.add(mapping)
    db.session.commit()
    flash('Мапінг додано', 'success')
    return redirect(url_for('integrations.wix_product_mappings_list'))


@integrations_bp.route('/integrations/wix-product-mappings/<int:mapping_id>/edit', methods=['POST'])
@login_required
def wix_product_mapping_edit(mapping_id):
    if not _is_admin_or_manager():
        abort(403)
    mapping = WixProductMapping.query.get_or_404(mapping_id)
    mapping.wix_item_name = (request.form.get('wix_item_name') or '').strip() or None
    mapping.order_scenario = request.form.get('order_scenario') or mapping.order_scenario
    mapping.delivery_type = (request.form.get('delivery_type') or '').strip() or None
    mapping.size = request.form.get('size') or mapping.size
    mapping.for_whom = (request.form.get('for_whom') or '').strip() or None
    mapping.is_active = request.form.get('is_active') == 'on'
    db.session.commit()
    flash('Мапінг оновлено', 'success')
    return redirect(url_for('integrations.wix_product_mappings_list'))


@integrations_bp.route('/integrations/wix-product-mappings/<int:mapping_id>/delete', methods=['POST'])
@login_required
def wix_product_mapping_delete(mapping_id):
    if not _is_admin_or_manager():
        abort(403)
    mapping = WixProductMapping.query.get_or_404(mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    flash('Мапінг видалено', 'success')
    return redirect(url_for('integrations.wix_product_mappings_list'))
```

```html
{# app/templates/integrations/product_mappings.html #}
{% extends "layout.html" %}
{% block content %}
<div class="container-fluid">
    <h2 class="mb-4">Мапінг товарів Wix</h2>

    <table class="table table-hover align-middle mb-5">
        <thead>
            <tr>
                <th>catalog_item_id</th>
                <th>Назва на сайті</th>
                <th>Сценарій</th>
                <th>Тип підписки</th>
                <th>Розмір</th>
                <th>Для кого</th>
                <th>Активний</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {% for m in mappings %}
            <tr>
                <form method="post" action="{{ url_for('integrations.wix_product_mapping_edit', mapping_id=m.id) }}">
                <td><code>{{ m.catalog_item_id }}</code></td>
                <td><input type="text" name="wix_item_name" class="form-control form-control-sm" value="{{ m.wix_item_name or '' }}"></td>
                <td>
                    <select name="order_scenario" class="form-select form-select-sm">
                        <option value="order" {% if m.order_scenario == 'order' %}selected{% endif %}>Разове</option>
                        <option value="subscription" {% if m.order_scenario == 'subscription' %}selected{% endif %}>Підписка</option>
                    </select>
                </td>
                <td><input type="text" name="delivery_type" class="form-control form-control-sm" value="{{ m.delivery_type or '' }}" placeholder="Weekly/Monthly/Bi-weekly"></td>
                <td><input type="text" name="size" class="form-control form-control-sm" value="{{ m.size }}" required></td>
                <td><input type="text" name="for_whom" class="form-control form-control-sm" value="{{ m.for_whom or '' }}"></td>
                <td><input type="checkbox" name="is_active" {% if m.is_active %}checked{% endif %}></td>
                <td>
                    <button type="submit" class="btn btn-sm btn-outline-primary">Зберегти</button>
                </td>
                </form>
                <td>
                    <form method="post" action="{{ url_for('integrations.wix_product_mapping_delete', mapping_id=m.id) }}" onsubmit="return confirm('Видалити мапінг?');">
                        <button type="submit" class="btn btn-sm btn-outline-danger">Видалити</button>
                    </form>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="8" class="text-center text-muted">Мапінгів ще немає</td></tr>
            {% endfor %}
        </tbody>
    </table>

    <h4 class="mb-3">Новий мапінг</h4>
    <form method="post" action="{{ url_for('integrations.wix_product_mapping_create') }}" class="row g-3">
        <div class="col-md-3">
            <label class="form-label">catalog_item_id <span class="text-danger">*</span></label>
            <input type="text" name="catalog_item_id" class="form-control" required>
        </div>
        <div class="col-md-3">
            <label class="form-label">Назва на сайті</label>
            <input type="text" name="wix_item_name" class="form-control">
        </div>
        <div class="col-md-2">
            <label class="form-label">Сценарій <span class="text-danger">*</span></label>
            <select name="order_scenario" class="form-select" required>
                <option value="order">Разове</option>
                <option value="subscription">Підписка</option>
            </select>
        </div>
        <div class="col-md-2">
            <label class="form-label">Тип підписки</label>
            <input type="text" name="delivery_type" class="form-control" placeholder="Weekly/Monthly/Bi-weekly">
        </div>
        <div class="col-md-1">
            <label class="form-label">Розмір <span class="text-danger">*</span></label>
            <input type="text" name="size" class="form-control" required>
        </div>
        <div class="col-md-1">
            <label class="form-label">Для кого</label>
            <input type="text" name="for_whom" class="form-control">
        </div>
        <div class="col-12">
            <button type="submit" class="btn btn-primary">Додати мапінг</button>
        </div>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_webhook_routes.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/blueprints/integrations/routes.py app/templates/integrations/product_mappings.html \
        tests/unit/test_wix_webhook_routes.py
git commit -m "feat: add Wix product mapping CRUD"
```

---

### Task 10: Navigation entry

**Files:**
- Modify: `app/templates/layout.html`

**Interfaces:**
- Consumes: `integrations.wix_leads_list` endpoint (Task 8).

- [ ] **Step 1: Add the mobile nav link**

In `app/templates/layout.html`, insert right after the closing `</a>` of the "Лог змін" link (originally lines 270-275) and before the "Завдання" link (still inside the `{% if current_user.user_type == 'admin' or current_user.has_role('admin') %}` block that opened at line 269):

```html
        <a href="/activity-log" onclick="closeMobileSidebar()"
           class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors
                  {% if request.path.startswith('/activity-log') %}bg-amber-50 border border-amber-200 text-amber-700{% else %}text-stone-600 hover:bg-stone-200 hover:text-stone-900{% endif %}">
            <i class="bi bi-shield-check text-lg flex-shrink-0"></i>
            <span>Лог змін</span>
        </a>
        <a href="{{ url_for('integrations.wix_leads_list') }}" onclick="closeMobileSidebar()"
           class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors
                  {% if request.path.startswith('/integrations') %}bg-amber-50 border border-amber-200 text-amber-700{% else %}text-stone-600 hover:bg-stone-200 hover:text-stone-900{% endif %}">
            <i class="bi bi-cloud-arrow-down text-lg flex-shrink-0"></i>
            <span>Заявки з сайту</span>
        </a>
```

- [ ] **Step 2: Add the desktop nav link**

Find the desktop-sidebar counterpart of the "Лог змін" link (around line 412, inside the equivalent admin-only `{% if %}` block for the desktop `<nav>`) and add the matching entry directly after it, mirroring the desktop link style (`title="..."` attribute, `<span class="nav-label">`) used by neighboring desktop entries:

```html
        <a href="{{ url_for('integrations.wix_leads_list') }}"
           class="flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors
                  {% if request.path.startswith('/integrations') %}bg-amber-50 border border-amber-200 text-amber-700{% else %}text-stone-600 hover:bg-stone-200 hover:text-stone-900{% endif %}"
           title="Заявки з сайту">
            <i class="bi bi-cloud-arrow-down text-lg flex-shrink-0"></i>
            <span class="nav-label">Заявки з сайту</span>
        </a>
```

- [ ] **Step 3: Manually verify**

Run: `grep -c "wix_leads_list" app/templates/layout.html`
Expected: `2` (one mobile, one desktop)

- [ ] **Step 4: Commit**

```bash
git add app/templates/layout.html
git commit -m "feat: add Заявки з сайту nav link for admin/manager"
```

---

### Task 11: `order_form()` prefill from `lead_id`

**Files:**
- Modify: `app/blueprints/orders/routes.py:197-208`
- Test: `tests/unit/test_wix_order_prefill.py`

**Interfaces:**
- Consumes: `WixLead` (Task 1), `wix_integration_service.find_product_mapping` (Task 3).
- Produces: `orders/form.html` template context gains `wix_lead: WixLead | None` and `wix_mapping: WixProductMapping | None` — used by Task 12.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_order_prefill.py
from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping
from app.models.user import User


def _login(app, client, user):
    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user.id)
        flask_session['_fresh'] = True


def _make_manager(session):
    user = User(username='mgr', email='mgr@example.com', user_type='manager', is_active=True)
    user.set_password('secret')
    session.add(user)
    session.commit()
    return user


def test_order_form_prefills_from_new_lead(app, session):
    manager = _make_manager(session)
    mapping = WixProductMapping(
        catalog_item_id='cat-1', order_scenario='subscription',
        delivery_type='Monthly', size='M', for_whom='Дружина',
    )
    lead = WixLead(
        wix_order_id='o-10', raw_payload={}, status='new',
        contact_name='Влад Білобров', contact_phone='+380666746225',
        city='Київ', street='вул. Зарічна, 1Г', catalog_item_id='cat-1',
        wix_order_number='10255', amount='6800.00', currency='UAH',
    )
    session.add_all([mapping, lead])
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.get(f'/orders/new?lead_id={lead.id}')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Влад Білобров' in html
    assert '+380666746225' in html
    assert 'вул. Зарічна, 1Г' in html
    assert '10255' in html


def test_order_form_ignores_already_processed_lead(app, session):
    manager = _make_manager(session)
    lead = WixLead(
        wix_order_id='o-11', raw_payload={}, status='processed',
        contact_name='Не Показувати',
    )
    session.add(lead)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.get(f'/orders/new?lead_id={lead.id}')

    assert resp.status_code == 200
    assert 'Не Показувати' not in resp.get_data(as_text=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_order_prefill.py -v`
Expected: FAIL (assertions on prefilled values not found in HTML, since route doesn't pass `wix_lead` yet)

- [ ] **Step 3: Modify `order_form()`**

In `app/blueprints/orders/routes.py`, replace lines 197-208:

```python
@orders_bp.route('/orders/new', methods=['GET'])
@login_required
def order_form():
    clients = Client.query.all()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.sort_order.nullslast(), Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template(
        'orders/form.html',
        clients=clients, cities=cities, delivery_types=delivery_types, sizes=sizes, for_whom=for_whom
    )
```

with:

```python
@orders_bp.route('/orders/new', methods=['GET'])
@login_required
def order_form():
    clients = Client.query.all()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.sort_order.nullslast(), Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()

    wix_lead = None
    wix_mapping = None
    lead_id = request.args.get('lead_id', type=int)
    if lead_id:
        from app.models.wix_lead import WixLead
        from app.services.wix_integration_service import find_product_mapping
        candidate = WixLead.query.get(lead_id)
        if candidate and candidate.status == 'new':
            wix_lead = candidate
            wix_mapping = find_product_mapping(candidate.catalog_item_id)

    return render_template(
        'orders/form.html',
        clients=clients, cities=cities, delivery_types=delivery_types, sizes=sizes, for_whom=for_whom,
        wix_lead=wix_lead, wix_mapping=wix_mapping,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_order_prefill.py -v`
Expected: still FAIL at this point — the route now passes `wix_lead`/`wix_mapping`, but `orders/form.html` doesn't render them yet. That template change is Task 12; this task's own test target is only that the route doesn't error and passes the right context. Replace the assertions temporarily is unnecessary — proceed to Task 12 before expecting these tests green. Run instead:

Run: `pytest tests/unit/test_wix_order_prefill.py -v -k processed_lead`
Expected: `test_order_form_ignores_already_processed_lead` PASSES already (nothing to prefill either way). Leave `test_order_form_prefills_from_new_lead` red — it will go green at the end of Task 12.

- [ ] **Step 5: Commit**

```bash
git add app/blueprints/orders/routes.py tests/unit/test_wix_order_prefill.py
git commit -m "feat: load Wix lead context for order form prefill"
```

---

### Task 12: `orders/form.html` prefill rendering

**Files:**
- Modify: `app/templates/orders/form.html`
- Test: `tests/unit/test_wix_order_prefill.py` (from Task 11, now expected to go green)

**Interfaces:**
- Consumes: `wix_lead` / `wix_mapping` context variables (Task 11).
- Produces: rendered `<input name="lead_id">`, `<input name="client_id">` hidden fields — consumed by Task 13's `order_create()`.

- [ ] **Step 1: Confirm the still-red test**

Run: `pytest tests/unit/test_wix_order_prefill.py::test_order_form_prefills_from_new_lead -v`
Expected: FAIL (assertions not found in HTML)

- [ ] **Step 2: Edit `orders/form.html`**

Add the hidden `lead_id` field right after the form tag. Replace:

```html
    <form method="post" class="row g-3" id="orderForm">
        <!-- Клієнт -->
```

with:

```html
    <form method="post" class="row g-3" id="orderForm">
        {% if wix_lead %}
        <input type="hidden" name="lead_id" value="{{ wix_lead.id }}">
        {% endif %}
        <!-- Клієнт -->
```

Add the hidden `client_id` field and relax the `client_instagram` requirement when a lead already matched a client. Replace:

```html
        <div class="col-md-6">
            <label class="form-label">Клієнт <span class="text-danger">*</span></label>
            <div class="position-relative">
                <input type="text" class="form-control" id="client-search" name="client_instagram" 
                       placeholder="Введіть Instagram клієнта..." required autocomplete="off">
                <div class="list-group position-absolute w-100 d-none" id="client-results" 
                     style="z-index: 1000; max-height: 200px; overflow-y: auto;"></div>
            </div>
        </div>
```

with:

```html
        <div class="col-md-6">
            <label class="form-label">Клієнт <span class="text-danger">*</span></label>
            <div class="position-relative">
                <input type="hidden" name="client_id" value="{{ wix_lead.matched_client_id or '' }}">
                <input type="text" class="form-control" id="client-search" name="client_instagram"
                       placeholder="Введіть Instagram клієнта..." autocomplete="off"
                       {% if not (wix_lead and wix_lead.matched_client_id) %}required{% endif %}
                       {% if wix_lead and wix_lead.matched_client_id %}value="{{ wix_lead.matched_client.display_name }}"{% endif %}>
                <div class="list-group position-absolute w-100 d-none" id="client-results" 
                     style="z-index: 1000; max-height: 200px; overflow-y: auto;"></div>
            </div>
            {% if wix_lead and not wix_lead.matched_client_id %}
            <div class="form-text text-warning">Клієнта з сайту не знайдено в CRM за телефоном/email — оберіть або створіть вручну.</div>
            {% endif %}
        </div>
```

Prefill recipient fields. Replace:

```html
        <div class="col-md-6">
            <label class="form-label">Ім'я отримувача <span class="text-danger">*</span></label>
            <input type="text" name="recipient_name" class="form-control" required>
        </div>
        
        <div class="col-md-6">
            <label class="form-label">Номер телефону отримувача <span class="text-danger">*</span></label>
            <input type="text" name="recipient_phone" class="form-control" required 
                   placeholder="+380" pattern="\+380[0-9]{9}">
        </div>
```

with:

```html
        <div class="col-md-6">
            <label class="form-label">Ім'я отримувача <span class="text-danger">*</span></label>
            <input type="text" name="recipient_name" class="form-control" required value="{{ wix_lead.contact_name or '' }}">
        </div>
        
        <div class="col-md-6">
            <label class="form-label">Номер телефону отримувача <span class="text-danger">*</span></label>
            <input type="text" name="recipient_phone" class="form-control" required 
                   placeholder="+380" pattern="\+380[0-9]{9}" value="{{ wix_lead.contact_phone or '' }}">
        </div>
```

Prefill the address. Replace:

```html
            <input type="text" name="city" id="form-city-input"
                   class="form-control" placeholder="Введіть місто або село"
                   required autocomplete="off">
```

with:

```html
            <input type="text" name="city" id="form-city-input"
                   class="form-control" placeholder="Введіть місто або село"
                   required autocomplete="off" value="{{ wix_lead.city or '' }}">
```

and replace:

```html
            <input type="text" name="street" id="address-input" class="form-control" required>
```

with:

```html
            <input type="text" name="street" id="address-input" class="form-control" required value="{{ wix_lead.street or '' }}">
```

Preselect `delivery_type` from the mapping (only meaningful for the `subscription` scenario). Replace:

```html
                {% if delivery_types and delivery_types|length > 0 %}
                    {% for t in delivery_types %}
                        <option value="{{ t.value }}">{{ t.value }}</option>
                    {% endfor %}
                {% else %}
```

with:

```html
                {% if delivery_types and delivery_types|length > 0 %}
                    {% for t in delivery_types %}
                        <option value="{{ t.value }}" {% if wix_mapping and wix_mapping.order_scenario == 'subscription' and wix_mapping.delivery_type == t.value %}selected{% endif %}>{{ t.value }}</option>
                    {% endfor %}
                {% else %}
```

Preselect `size`. Replace:

```html
                {% if sizes and sizes|length > 0 %}
                    {% for s in sizes %}
                        <option value="{{ s.value }}">{{ s.value }}</option>
                    {% endfor %}
                {% else %}
```

with:

```html
                {% if sizes and sizes|length > 0 %}
                    {% for s in sizes %}
                        <option value="{{ s.value }}" {% if wix_mapping and wix_mapping.size == s.value %}selected{% endif %}>{{ s.value }}</option>
                    {% endfor %}
                {% else %}
```

Preselect `for_whom`. Replace:

```html
                {% if for_whom and for_whom|length > 0 %}
                    {% for f in for_whom %}
                        <option value="{{ f.value }}">{{ f.value }}</option>
                    {% endfor %}
                {% else %}
```

with:

```html
                {% if for_whom and for_whom|length > 0 %}
                    {% for f in for_whom %}
                        <option value="{{ f.value }}" {% if wix_mapping and wix_mapping.for_whom == f.value %}selected{% endif %}>{{ f.value }}</option>
                    {% endfor %}
                {% else %}
```

Add a reference comment. Replace:

```html
            <textarea name="comment" class="form-control" rows="3" placeholder="Додаткові коментарі..."></textarea>
```

with:

```html
            <textarea name="comment" class="form-control" rows="3" placeholder="Додаткові коментарі...">{% if wix_lead %}Заявка з сайту #{{ wix_lead.wix_order_number }} ({{ wix_lead.amount }} {{ wix_lead.currency }}){% endif %}</textarea>
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_order_prefill.py -v`
Expected: both tests PASS

- [ ] **Step 4: Regenerate Tailwind build (per CLAUDE.md — new classes weren't added, but confirm no build step is required)**

No new Tailwind utility classes were introduced (only Bootstrap classes already present in this template), so `npm run build` is not required for this task.

- [ ] **Step 5: Commit**

```bash
git add app/templates/orders/form.html tests/unit/test_wix_order_prefill.py
git commit -m "feat: prefill order form from Wix lead"
```

---

### Task 13: Mark lead processed on order/subscription creation

**Files:**
- Modify: `app/blueprints/orders/routes.py:211-414` (`order_create`)
- Test: `tests/unit/test_wix_order_prefill.py`

**Interfaces:**
- Consumes: `wix_integration_service.mark_lead_processed` (Task 5); `WixLead` (Task 1).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_wix_order_prefill.py (append)
from app.models import Client


def test_order_create_marks_lead_processed(app, session):
    manager = _make_manager(session)
    client_obj = Client(instagram='vlad_flowers', phone='+380666746225')
    lead = WixLead(wix_order_id='o-20', raw_payload={}, status='new')
    session.add_all([client_obj, lead])
    session.commit()

    web_client = app.test_client()
    _login(app, web_client, manager)

    resp = web_client.post('/orders/new', data={
        'lead_id': str(lead.id),
        'client_id': str(client_obj.id),
        'recipient_name': 'Влад Білобров',
        'recipient_phone': '+380666746225',
        'city': 'Київ',
        'street': 'вул. Зарічна, 1Г',
        'delivery_type': 'Разова',
        'delivery_method': 'courier',
        'size': 'M',
        'first_delivery_date': '2026-09-01',
        'for_whom': 'Дружина',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = WixLead.query.get(lead.id)
    assert updated.status == 'processed'
    assert updated.processed_order_id is not None
    assert updated.processed_by_user_id == manager.id
```

Note: `delivery_type` value `'Разова'` must not be one of `SUBSCRIPTION_TYPES` (`Weekly`/`Monthly`/`Bi-weekly` per `CLAUDE.md`) so this creates a one-time `Order`, matching `processed_order_id` (not `processed_subscription_id`).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wix_order_prefill.py::test_order_create_marks_lead_processed -v`
Expected: FAIL — `updated.status == 'new'` (lead never touched)

- [ ] **Step 3: Modify `order_create()`**

In `app/blueprints/orders/routes.py`, locate this block (originally lines 400-405):

```python
    if certificate:
        from datetime import datetime as _dt
        certificate.status = 'used'
        certificate.used_at = _dt.utcnow()
        certificate.order_id = entity_id
        db.session.commit()
```

Insert the lead-processing logic immediately before it:

```python
    lead_id_raw = (request.form.get('lead_id') or '').strip()
    if lead_id_raw.isdigit():
        from app.models.wix_lead import WixLead
        from app.services.wix_integration_service import mark_lead_processed
        lead = WixLead.query.get(int(lead_id_raw))
        if lead and lead.status == 'new':
            mark_lead_processed(lead, entity, current_user)

    if certificate:
        from datetime import datetime as _dt
        certificate.status = 'used'
        certificate.used_at = _dt.utcnow()
        certificate.order_id = entity_id
        db.session.commit()
```

`current_user` is already imported in this file via `flask_login` (used elsewhere in the module for `login_required`/activity logging) — confirm with:

Run: `grep -n "^from flask_login" app/blueprints/orders/routes.py`
Expected: a line importing `current_user` from `flask_login`. If it isn't imported yet, add it to that import line.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wix_order_prefill.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/blueprints/orders/routes.py tests/unit/test_wix_order_prefill.py
git commit -m "feat: mark Wix lead processed when its order/subscription is created"
```

---

### Task 14: Full-suite regression check and migration apply (local)

**Files:** none created; verification only.

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -v`
Expected: all tests PASS, including every `test_wix_*` test from Tasks 1-13 and all pre-existing tests (no regressions in `orders`, `subscriptions`, `dashboard`, etc.)

- [ ] **Step 2: Apply the migration locally (only after all commits above are in git)**

```bash
git status
flask db upgrade
```

Expected: `wix_lead` and `wix_product_mapping` tables created with no errors, and `git status` shows a clean tree (the migration file was already committed in Task 1).

- [ ] **Step 3: Manual smoke test of the webhook with the real sample payload**

With the dev server running and `WIX_ALLOWED_SITE_IDS=2c31eac1-a4f1-4fd2-886d-361377a42a1f` set in `.env`, POST the sample payload from the task (the `data` object, wrapped as `{"data": {...}}`) to `http://localhost:8002/api/integrations/wix/order-placed` and confirm:
- Response is `200 {"ok": true, "lead_id": N}`
- The lead appears at `/integrations/wix-leads` with item name, amount, and contact prefilled
- `/orders/new?lead_id=N` shows the prefilled form
- Submitting it creates the order and flips the lead to `processed` in `/integrations/wix-leads?status=processed`

- [ ] **Step 4: Commit (only if smoke testing required fixes)**

If Step 3 surfaces bugs, fix them with a normal commit; otherwise this task ends without a commit since no files changed.

---

## Environment setup reminder (not a code task)

Document for the user, not an automated step: set `WIX_ALLOWED_SITE_IDS` in `.env` and in the deployed environment's secrets to the real site's `metaSiteId` (`2c31eac1-a4f1-4fd2-886d-361377a42a1f` per the sample payload) before pointing the real Wix Automation at the new endpoint. Configure the Wix Automation's "Send an HTTP request" action to POST the full trigger payload (`{{data}}`, wrapped as `{"data": ...}`) to `https://<your-domain>/api/integrations/wix/order-placed`.
