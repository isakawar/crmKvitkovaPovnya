# Manager Telegram Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a new Wix lead arrives, every admin/manager `User` who has linked their Telegram gets a message with a "Перейти до замовлення" button pointing at the prefilled order form; once the lead is processed (by anyone, in the CRM), every sent message's button is edited to point at the created order instead.

**Architecture:** Extends `User` with the same Telegram-linkage fields `Courier` already has, and extends the existing courier `/register`/contact-share bot flow to also match admin/manager `User`s by phone — no new bot commands. A new `wix_lead_notification` table records one row per sent Telegram message (lead × recipient) so each can be individually edited later. A new `app/telegram_bot/manager_notification_service.py` mirrors the existing sync-Flask-to-async-PTB bridge already used by `TelegramNotificationService`.

**Tech Stack:** Flask, Flask-SQLAlchemy, python-telegram-bot (already integrated), Alembic, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-manager-telegram-notifications-design.md`

## Global Constraints

- Business logic only in `app/services/`/`app/telegram_bot/*_service.py` — routes and bot handlers stay thin.
- Migration `down_revision` must be the actual current head — verify via the same grep-based head-finder used in prior migrations on this branch. At plan-writing time the head is `add_wix_integration_tables`; re-verify live before writing the file.
- `Courier.phone`/`telegram_chat_id` matching always takes priority over `User` matching in the bot's registration flow — a `User` lookup only happens after `Courier.query.filter_by(phone=phone).first()` returns nothing.
- `current_app.telegram_bot` (the `TelegramBot` object, not raw HTTP) is the interface used for sending/editing — mirrors `TelegramNotificationService`, not the raw-HTTP `_telegram_send`/`_telegram_edit` helpers in `app/blueprints/routes/routes.py`.
- Reuse `app.services.csv_import_service.normalize_phone` for phone normalization — already imported in `app/telegram_bot/handlers.py`, do not duplicate.
- Cross-module calls between `app/services/wix_integration_service.py` and `app/telegram_bot/manager_notification_service.py`, and between `app/blueprints/integrations/routes.py` and the same service, use function-local imports (the established convention throughout this codebase for cross-package service calls — confirmed during the prior Wix-integration plan's review as intentional, not sloppy).
- A failed/blocked Telegram send or edit for one recipient must never raise past the calling code (webhook processing / order creation must always succeed regardless of Telegram delivery problems) — log and continue.

---

## File Structure

**New files:**
- `app/models/wix_lead_notification.py` — `WixLeadNotification` model
- `migrations/versions/add_user_telegram_and_lead_notifications.py` — adds `User` columns + creates `wix_lead_notification`
- `app/telegram_bot/manager_notification_service.py` — `send_new_lead_notification`, `notify_lead_processed`
- `tests/unit/test_manager_notification_service.py`
- `tests/unit/test_telegram_manager_matching.py`
- `tests/unit/test_settings_users_telegram.py`

**Modified files:**
- `app/models/user.py` — add Telegram/phone columns
- `app/models/__init__.py` — register `WixLeadNotification`
- `app/config.py` — `CRM_PUBLIC_URL`
- `app/telegram_bot/services.py` — `find_manager_by_phone`
- `app/telegram_bot/handlers.py` — `register_command`, `handle_contact` extended to also match `User`
- `app/blueprints/integrations/routes.py` — `wix_order_webhook` triggers notification for genuinely-new leads
- `app/services/wix_integration_service.py` — `mark_lead_processed` triggers message edits
- `app/blueprints/settings/routes.py` — `get_users`, `create_user`, `update_user` handle `phone`; new `reset_user_telegram` route
- `app/templates/settings/users.html` — phone field in create/edit modals, Telegram status column, reset button

---

### Task 1: `User` Telegram fields, `WixLeadNotification` model, migration

**Files:**
- Modify: `app/models/user.py`
- Create: `app/models/wix_lead_notification.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/add_user_telegram_and_lead_notifications.py`
- Test: `tests/unit/test_manager_notification_service.py` (model smoke-test only in this task)

**Interfaces:**
- Produces: `User` columns `phone, telegram_chat_id, telegram_username, telegram_registered, telegram_notifications_enabled, last_telegram_activity` — used by Tasks 3-7.
- Produces: `WixLeadNotification` columns `id, wix_lead_id, user_id, telegram_chat_id, telegram_message_id, sent_at` — used by Tasks 3-5.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_manager_notification_service.py
from app.models import Client
from app.models.user import User
from app.models.wix_lead import WixLead
from app.models.wix_lead_notification import WixLeadNotification


def test_user_telegram_fields_and_notification_model_roundtrip(session):
    user = User(
        username='mgr1', email='mgr1@example.com', user_type='manager',
        phone='+380661112233', telegram_chat_id=555111,
        telegram_username='mgr_tg', telegram_registered=True,
    )
    user.set_password('secret')
    lead = WixLead(wix_order_id='order-tg-1', raw_payload={}, status='new')
    session.add_all([user, lead])
    session.commit()

    notification = WixLeadNotification(
        wix_lead_id=lead.id, user_id=user.id,
        telegram_chat_id=user.telegram_chat_id, telegram_message_id=42,
    )
    session.add(notification)
    session.commit()

    fetched_user = User.query.filter_by(username='mgr1').first()
    assert fetched_user.phone == '+380661112233'
    assert fetched_user.telegram_chat_id == 555111
    assert fetched_user.telegram_notifications_enabled is True

    fetched = WixLeadNotification.query.filter_by(wix_lead_id=lead.id).first()
    assert fetched.user_id == user.id
    assert fetched.telegram_message_id == 42
    assert fetched.sent_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_manager_notification_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.wix_lead_notification'`

- [ ] **Step 3: Modify `User` model**

In `app/models/user.py`, add after the `calculator_prefs` line:

```python
    calculator_prefs = db.Column(db.Text, nullable=True)

    # Telegram integration (mirrors Courier's fields)
    phone = db.Column(db.String(32), unique=True, nullable=True)
    telegram_chat_id = db.Column(db.BigInteger, unique=True, nullable=True)
    telegram_username = db.Column(db.String(64), nullable=True)
    telegram_registered = db.Column(db.Boolean, default=False, nullable=False)
    telegram_notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_telegram_activity = db.Column(db.DateTime, nullable=True)
```

- [ ] **Step 4: Create `WixLeadNotification` model**

```python
# app/models/wix_lead_notification.py
from datetime import datetime

from app.extensions import db


class WixLeadNotification(db.Model):
    __tablename__ = 'wix_lead_notification'

    id = db.Column(db.Integer, primary_key=True)
    wix_lead_id = db.Column(db.Integer, db.ForeignKey('wix_lead.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    telegram_chat_id = db.Column(db.BigInteger, nullable=False)
    telegram_message_id = db.Column(db.Integer, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lead = db.relationship('WixLead', foreign_keys=[wix_lead_id])
    user = db.relationship('User', foreign_keys=[user_id])
```

Register in `app/models/__init__.py` — add after `from .wix_product_mapping import WixProductMapping`:

```python
from .wix_lead_notification import WixLeadNotification
```

And add `'WixLeadNotification'` to the `__all__` list.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_manager_notification_service.py -v`
Expected: PASS

- [ ] **Step 6: Write the migration**

First confirm the current head:

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

Expected output: `HEADS: {'add_wix_integration_tables'}`. If it differs, use the actual head as `down_revision` instead.

```python
# migrations/versions/add_user_telegram_and_lead_notifications.py
"""Add Telegram fields to User and wix_lead_notification table

Revision ID: add_user_telegram_and_lead_notifications
Revises: add_wix_integration_tables
Create Date: 2026-08-24
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_user_telegram_and_lead_notifications'
down_revision = 'add_wix_integration_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('phone', sa.String(length=32), nullable=True))
    op.add_column('user', sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True))
    op.add_column('user', sa.Column('telegram_username', sa.String(length=64), nullable=True))
    op.add_column('user', sa.Column('telegram_registered', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('user', sa.Column('telegram_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('user', sa.Column('last_telegram_activity', sa.DateTime(), nullable=True))
    op.create_unique_constraint('uq_user_phone', 'user', ['phone'])
    op.create_unique_constraint('uq_user_telegram_chat_id', 'user', ['telegram_chat_id'])

    op.create_table(
        'wix_lead_notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wix_lead_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('telegram_message_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['wix_lead_id'], ['wix_lead.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_wix_lead_notification_wix_lead_id', 'wix_lead_notification', ['wix_lead_id'])


def downgrade():
    op.drop_index('ix_wix_lead_notification_wix_lead_id', table_name='wix_lead_notification')
    op.drop_table('wix_lead_notification')
    op.drop_constraint('uq_user_telegram_chat_id', 'user', type_='unique')
    op.drop_constraint('uq_user_phone', 'user', type_='unique')
    op.drop_column('user', 'last_telegram_activity')
    op.drop_column('user', 'telegram_notifications_enabled')
    op.drop_column('user', 'telegram_registered')
    op.drop_column('user', 'telegram_username')
    op.drop_column('user', 'telegram_chat_id')
    op.drop_column('user', 'phone')
```

**Do not run `flask db upgrade` yet — commit first (per CLAUDE.md migration rule).**

- [ ] **Step 7: Commit**

```bash
git add app/models/user.py app/models/wix_lead_notification.py app/models/__init__.py \
        migrations/versions/add_user_telegram_and_lead_notifications.py \
        tests/unit/test_manager_notification_service.py
git commit -m "feat: add User Telegram fields and WixLeadNotification model"
```

---

### Task 2: `CRM_PUBLIC_URL` config

**Files:**
- Modify: `app/config.py`

**Interfaces:**
- Produces: `current_app.config['CRM_PUBLIC_URL']` — used by Tasks 3-4.

- [ ] **Step 1: Add the config value**

In `app/config.py`, inside `class Config:` add right after the `WIX_ALLOWED_SITE_IDS` line:

```python
    WIX_ALLOWED_SITE_IDS = os.environ.get('WIX_ALLOWED_SITE_IDS', '')

    # Base URL used to build links inside Telegram notifications (localhost
    # is unreachable from a manager's phone) — e.g. https://crm.example.com
    CRM_PUBLIC_URL = os.environ.get('CRM_PUBLIC_URL', '')
```

And inside `class DevelopmentConfig:` add right after its own `WIX_ALLOWED_SITE_IDS` line:

```python
    WIX_ALLOWED_SITE_IDS = os.environ.get('WIX_ALLOWED_SITE_IDS', '')

    # Base URL used to build links inside Telegram notifications (localhost
    # is unreachable from a manager's phone) — e.g. https://crm.example.com
    CRM_PUBLIC_URL = os.environ.get('CRM_PUBLIC_URL', '')
```

- [ ] **Step 2: Verify by import**

Run: `python3 -c "from app.config import Config, DevelopmentConfig; print(repr(Config.CRM_PUBLIC_URL), repr(DevelopmentConfig.CRM_PUBLIC_URL))"`
Expected: prints two empty strings, no `AttributeError`

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat: add CRM_PUBLIC_URL config for Telegram notification links"
```

---

### Task 3: `send_new_lead_notification`

**Files:**
- Create: `app/telegram_bot/manager_notification_service.py`
- Test: `tests/unit/test_manager_notification_service.py`

**Interfaces:**
- Consumes: `app.models.user.User`, `app.models.wix_lead_notification.WixLeadNotification`, `app.models.wix_lead.WixLead`, `current_app.telegram_bot` (`.is_initialized()`, async `.send_message(chat_id, text, reply_markup=None) -> Optional[int]`), `current_app.config['CRM_PUBLIC_URL']`.
- Produces: `send_new_lead_notification(lead: WixLead) -> int` (count of successfully sent messages) — used by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_manager_notification_service.py (append)
class FakeTelegramBot:
    """Minimal stand-in for TelegramBot — no real network calls."""

    def __init__(self, initialized=True):
        self._initialized = initialized
        self.sent = []
        self.edited = []
        self._next_id = 1000

    def is_initialized(self):
        return self._initialized

    async def send_message(self, chat_id, text, reply_markup=None):
        self._next_id += 1
        self.sent.append({'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup})
        return self._next_id

    async def edit_message(self, chat_id, message_id, text, reply_markup=None):
        self.edited.append({
            'chat_id': chat_id, 'message_id': message_id,
            'text': text, 'reply_markup': reply_markup,
        })
        return True


def _make_lead(session, **overrides):
    defaults = dict(
        wix_order_id='order-notify-1', wix_order_number='9001', raw_payload={}, status='new',
        contact_name='Влад Білобров', contact_phone='+380666746225',
        item_name='Букет S', amount='1200.00', currency='UAH',
    )
    defaults.update(overrides)
    lead = WixLead(**defaults)
    session.add(lead)
    session.commit()
    return lead


def test_send_new_lead_notification_sends_to_all_linked_managers(app, session):
    from app.telegram_bot.manager_notification_service import send_new_lead_notification

    app.config['CRM_PUBLIC_URL'] = 'https://crm.example.com'
    app.telegram_bot = FakeTelegramBot()

    mgr1 = User(username='mgr1', email='mgr1@example.com', user_type='manager',
                telegram_chat_id=111, telegram_notifications_enabled=True)
    mgr1.set_password('x')
    mgr2 = User(username='mgr2', email='mgr2@example.com', user_type='admin',
                telegram_chat_id=222, telegram_notifications_enabled=True)
    mgr2.set_password('x')
    no_telegram = User(username='mgr3', email='mgr3@example.com', user_type='manager')
    no_telegram.set_password('x')
    disabled = User(username='mgr4', email='mgr4@example.com', user_type='manager',
                     telegram_chat_id=333, telegram_notifications_enabled=False)
    disabled.set_password('x')
    session.add_all([mgr1, mgr2, no_telegram, disabled])
    session.commit()

    lead = _make_lead(session)

    count = send_new_lead_notification(lead)

    assert count == 2
    sent_chat_ids = {m['chat_id'] for m in app.telegram_bot.sent}
    assert sent_chat_ids == {111, 222}
    assert 'https://crm.example.com/orders/new?lead_id=' + str(lead.id) in app.telegram_bot.sent[0]['reply_markup'].inline_keyboard[0][0].url

    notifications = WixLeadNotification.query.filter_by(wix_lead_id=lead.id).all()
    assert len(notifications) == 2
    assert {n.user_id for n in notifications} == {mgr1.id, mgr2.id}


def test_send_new_lead_notification_noop_when_bot_not_initialized(app, session):
    from app.telegram_bot.manager_notification_service import send_new_lead_notification

    app.config['CRM_PUBLIC_URL'] = 'https://crm.example.com'
    app.telegram_bot = FakeTelegramBot(initialized=False)

    mgr = User(username='mgr5', email='mgr5@example.com', user_type='manager', telegram_chat_id=444)
    mgr.set_password('x')
    session.add(mgr)
    session.commit()
    lead = _make_lead(session, wix_order_id='order-notify-2')

    count = send_new_lead_notification(lead)

    assert count == 0
    assert WixLeadNotification.query.count() == 0


def test_send_new_lead_notification_noop_when_public_url_missing(app, session):
    from app.telegram_bot.manager_notification_service import send_new_lead_notification

    app.config['CRM_PUBLIC_URL'] = ''
    app.telegram_bot = FakeTelegramBot()

    mgr = User(username='mgr6', email='mgr6@example.com', user_type='manager', telegram_chat_id=555)
    mgr.set_password('x')
    session.add(mgr)
    session.commit()
    lead = _make_lead(session, wix_order_id='order-notify-3')

    count = send_new_lead_notification(lead)

    assert count == 0
    assert len(app.telegram_bot.sent) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_manager_notification_service.py -v -k send_new_lead_notification`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.telegram_bot.manager_notification_service'`

- [ ] **Step 3: Write the implementation**

```python
# app/telegram_bot/manager_notification_service.py
import asyncio
import logging

from flask import current_app
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.extensions import db
from app.models.user import User
from app.models.wix_lead_notification import WixLeadNotification

logger = logging.getLogger(__name__)


def _format_lead_message(lead) -> str:
    lines = [f"🆕 Нова заявка з сайту #{lead.wix_order_number or lead.id}", ""]
    if lead.contact_name:
        lines.append(lead.contact_name)
    if lead.contact_phone:
        lines.append(lead.contact_phone)
    lines.append("")
    if lead.item_name:
        lines.append(lead.item_name)
    if lead.amount is not None:
        lines.append(f"{lead.amount} {lead.currency or ''}".strip())
    return "\n".join(lines)


def send_new_lead_notification(lead) -> int:
    """Notify all Telegram-linked admin/manager users about a new Wix lead.

    Returns the number of successfully sent notifications.
    """
    if not hasattr(current_app, 'telegram_bot') or not current_app.telegram_bot.is_initialized():
        logger.warning('Telegram bot not initialized, skipping new lead notification')
        return 0

    base_url = current_app.config.get('CRM_PUBLIC_URL')
    if not base_url:
        logger.warning('CRM_PUBLIC_URL not configured, skipping new lead notification')
        return 0

    recipients = User.query.filter(
        User.telegram_chat_id.isnot(None),
        User.telegram_notifications_enabled.is_(True),
        User.user_type.in_(('admin', 'manager')),
    ).all()
    if not recipients:
        return 0

    text = _format_lead_message(lead)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            '🛒 Перейти до замовлення',
            url=f'{base_url}/orders/new?lead_id={lead.id}',
        )
    ]])

    bot = current_app.telegram_bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success_count = loop.run_until_complete(
            _send_to_all(bot, recipients, lead.id, text, keyboard)
        )
    finally:
        loop.close()
    return success_count


async def _send_to_all(bot, recipients, lead_id, text, keyboard) -> int:
    success_count = 0
    for user in recipients:
        message_id = await bot.send_message(
            chat_id=user.telegram_chat_id, text=text, reply_markup=keyboard,
        )
        if not message_id:
            continue
        db.session.add(WixLeadNotification(
            wix_lead_id=lead_id,
            user_id=user.id,
            telegram_chat_id=user.telegram_chat_id,
            telegram_message_id=message_id,
        ))
        success_count += 1
    db.session.commit()
    return success_count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_manager_notification_service.py -v -k send_new_lead_notification`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/telegram_bot/manager_notification_service.py tests/unit/test_manager_notification_service.py
git commit -m "feat: send Telegram notification to managers on new Wix lead"
```

---

### Task 4: `notify_lead_processed`

**Files:**
- Modify: `app/telegram_bot/manager_notification_service.py`
- Test: `tests/unit/test_manager_notification_service.py`

**Interfaces:**
- Consumes: `WixLeadNotification`, `current_app.telegram_bot.edit_message(chat_id, message_id, text, reply_markup=None) -> bool`, `_format_lead_message` (Task 3).
- Produces: `notify_lead_processed(lead: WixLead) -> int` — used by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_manager_notification_service.py (append)
def test_notify_lead_processed_edits_all_sent_messages(app, session):
    from app.telegram_bot.manager_notification_service import notify_lead_processed

    app.config['CRM_PUBLIC_URL'] = 'https://crm.example.com'
    app.telegram_bot = FakeTelegramBot()

    mgr1 = User(username='mgr7', email='mgr7@example.com', user_type='manager', telegram_chat_id=666)
    mgr1.set_password('x')
    mgr2 = User(username='mgr8', email='mgr8@example.com', user_type='manager', telegram_chat_id=777)
    mgr2.set_password('x')
    session.add_all([mgr1, mgr2])
    session.commit()

    lead = _make_lead(session, wix_order_id='order-notify-4')
    lead.status = 'processed'
    lead.processed_order_id = 999
    session.add_all([
        WixLeadNotification(wix_lead_id=lead.id, user_id=mgr1.id, telegram_chat_id=666, telegram_message_id=1),
        WixLeadNotification(wix_lead_id=lead.id, user_id=mgr2.id, telegram_chat_id=777, telegram_message_id=2),
    ])
    session.commit()

    count = notify_lead_processed(lead)

    assert count == 2
    assert len(app.telegram_bot.edited) == 2
    edited_chat_ids = {e['chat_id'] for e in app.telegram_bot.edited}
    assert edited_chat_ids == {666, 777}
    for edit in app.telegram_bot.edited:
        assert edit['reply_markup'].inline_keyboard[0][0].url == 'https://crm.example.com/orders/999/edit'
        assert 'Оброблено' in edit['reply_markup'].inline_keyboard[0][0].text


def test_notify_lead_processed_noop_when_no_notifications_sent(app, session):
    from app.telegram_bot.manager_notification_service import notify_lead_processed

    app.config['CRM_PUBLIC_URL'] = 'https://crm.example.com'
    app.telegram_bot = FakeTelegramBot()

    lead = _make_lead(session, wix_order_id='order-notify-5')
    lead.status = 'processed'
    lead.processed_order_id = 111
    session.commit()

    count = notify_lead_processed(lead)

    assert count == 0
    assert len(app.telegram_bot.edited) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_manager_notification_service.py -v -k notify_lead_processed`
Expected: FAIL with `ImportError: cannot import name 'notify_lead_processed'`

- [ ] **Step 3: Write the implementation**

Append to `app/telegram_bot/manager_notification_service.py`:

```python
def notify_lead_processed(lead) -> int:
    """Edit every sent Telegram notification for this lead to show it's processed.

    Returns the number of successfully edited messages.
    """
    if not hasattr(current_app, 'telegram_bot') or not current_app.telegram_bot.is_initialized():
        return 0

    notifications = WixLeadNotification.query.filter_by(wix_lead_id=lead.id).all()
    if not notifications:
        return 0

    base_url = current_app.config.get('CRM_PUBLIC_URL')
    if not base_url:
        return 0

    order_id = lead.processed_order_id
    url = f'{base_url}/orders/{order_id}/edit' if order_id else f'{base_url}/orders'

    text = _format_lead_message(lead) + '\n\n✅ Оброблено'
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton('✅ Оброблено — переглянути замовлення', url=url)
    ]])

    bot = current_app.telegram_bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success_count = loop.run_until_complete(_edit_all(bot, notifications, text, keyboard))
    finally:
        loop.close()
    return success_count


async def _edit_all(bot, notifications, text, keyboard) -> int:
    success_count = 0
    for notification in notifications:
        ok = await bot.edit_message(
            chat_id=notification.telegram_chat_id,
            message_id=notification.telegram_message_id,
            text=text,
            reply_markup=keyboard,
        )
        if ok:
            success_count += 1
    return success_count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_manager_notification_service.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/telegram_bot/manager_notification_service.py tests/unit/test_manager_notification_service.py
git commit -m "feat: edit manager Telegram notifications when a Wix lead is processed"
```

---

### Task 5: Wire the triggers

**Files:**
- Modify: `app/blueprints/integrations/routes.py`
- Modify: `app/services/wix_integration_service.py`
- Test: `tests/unit/test_manager_notification_service.py`

**Interfaces:**
- Consumes: `send_new_lead_notification`, `notify_lead_processed` (Tasks 3-4).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_manager_notification_service.py (append)
import json


def test_webhook_triggers_notification_only_for_genuinely_new_lead(app, session, monkeypatch):
    from tests.unit.test_wix_integration_service import SAMPLE_WIX_PAYLOAD
    import copy

    app.config['WIX_ALLOWED_SITE_IDS'] = '2c31eac1-a4f1-4fd2-886d-361377a42a1f'

    calls = []
    monkeypatch.setattr(
        'app.blueprints.integrations.routes.send_new_lead_notification',
        lambda lead: calls.append(lead.id) or 1,
    )

    client = app.test_client()
    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)

    resp1 = client.post('/api/integrations/wix/order-placed',
                         data=json.dumps(payload), content_type='application/json')
    assert resp1.status_code == 200
    assert len(calls) == 1

    # Same wix_order_id again (Wix retry) — must NOT notify a second time
    resp2 = client.post('/api/integrations/wix/order-placed',
                         data=json.dumps(payload), content_type='application/json')
    assert resp2.status_code == 200
    assert len(calls) == 1


def test_mark_lead_processed_triggers_notify(session, monkeypatch):
    from app.services.wix_integration_service import mark_lead_processed
    from app.models import Client
    from app.models.order import Order
    import datetime as _dt

    calls = []
    monkeypatch.setattr(
        'app.services.wix_integration_service.notify_lead_processed',
        lambda lead: calls.append(lead.id) or 1,
    )

    client_obj = Client(instagram='tguser')
    lead = _make_lead(session, wix_order_id='order-notify-6')
    session.add(client_obj)
    session.commit()
    order = Order(
        client_id=client_obj.id, recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', delivery_date=_dt.date.today(), for_whom='Дружина',
    )
    session.add(order)
    session.commit()

    manager = User(username='mgr9', email='mgr9@example.com', user_type='manager')
    manager.set_password('x')
    session.add(manager)
    session.commit()

    mark_lead_processed(lead, order, manager)

    assert calls == [lead.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_manager_notification_service.py -v -k "triggers_notification or triggers_notify"`
Expected: FAIL — `send_new_lead_notification`/`notify_lead_processed` are never called from the route/service yet, so `calls` stays empty and the assertions fail.

- [ ] **Step 3: Wire the webhook route**

In `app/blueprints/integrations/routes.py`, replace:

```python
    try:
        parsed = wix_service.parse_wix_payload(payload)
        lead = wix_service.create_or_update_lead(payload, parsed)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        logging.warning('Wix webhook: failed to parse/process payload', exc_info=True)
        return jsonify({'ok': False, 'error': 'malformed payload'}), 400

    logging.info(f'Wix webhook: lead {lead.id} (wix_order_id={lead.wix_order_id}) accepted')
    return jsonify({'ok': True, 'lead_id': lead.id}), 200
```

with:

```python
    try:
        parsed = wix_service.parse_wix_payload(payload)
        wix_order_id = parsed.get('wix_order_id')
        existing_before = (
            WixLead.query.filter_by(wix_order_id=wix_order_id).first() if wix_order_id else None
        )
        lead = wix_service.create_or_update_lead(payload, parsed)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        logging.warning('Wix webhook: failed to parse/process payload', exc_info=True)
        return jsonify({'ok': False, 'error': 'malformed payload'}), 400

    logging.info(f'Wix webhook: lead {lead.id} (wix_order_id={lead.wix_order_id}) accepted')

    if existing_before is None:
        from app.telegram_bot.manager_notification_service import send_new_lead_notification
        send_new_lead_notification(lead)

    return jsonify({'ok': True, 'lead_id': lead.id}), 200
```

- [ ] **Step 4: Wire `mark_lead_processed`**

In `app/services/wix_integration_service.py`, replace:

```python
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

with:

```python
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

    from app.telegram_bot.manager_notification_service import notify_lead_processed
    notify_lead_processed(lead)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_manager_notification_service.py -v`
Expected: all tests PASS

Then run the full Wix test files to confirm no regressions:

Run: `pytest tests/unit/test_wix_webhook_routes.py tests/unit/test_wix_order_prefill.py tests/unit/test_wix_integration_service.py -v`
Expected: all PASS (note: these tests do NOT mock `send_new_lead_notification`/`notify_lead_processed`, so they will exercise the real functions — since `WIX_ALLOWED_SITE_IDS`/`CRM_PUBLIC_URL`/`app.telegram_bot` are not fully configured in those test files' fixtures, the real functions must no-op safely rather than erroring, per Task 3/4's "noop when not configured" behavior. If any of these pre-existing tests fail because `app.telegram_bot` is unset entirely in the base `app` fixture, check `hasattr(current_app, 'telegram_bot')` — the base `create_app` in `tests/conftest.py` goes through the real `create_app()` factory which always sets `app.telegram_bot = TelegramBot()` per `app/__init__.py`, so this attribute always exists; `is_initialized()` will simply return `False` since `TELEGRAM_BOT_TOKEN` is unset in `TestingConfig`, and the noop path handles that.)

- [ ] **Step 6: Commit**

```bash
git add app/blueprints/integrations/routes.py app/services/wix_integration_service.py \
        tests/unit/test_manager_notification_service.py
git commit -m "feat: trigger manager Telegram notifications from the Wix lead lifecycle"
```

---

### Task 6: Bot registration matches admin/manager `User`s too

**Files:**
- Modify: `app/telegram_bot/services.py`
- Modify: `app/telegram_bot/handlers.py`
- Test: `tests/unit/test_telegram_manager_matching.py`

**Interfaces:**
- Produces: `find_manager_by_phone(phone: str) -> User | None` — a module-level function in `app/telegram_bot/services.py`, used by the two handler functions modified in this task.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_telegram_manager_matching.py
from app.models.user import User


def test_find_manager_by_phone_matches_active_admin_or_manager(session):
    from app.telegram_bot.services import find_manager_by_phone

    manager = User(username='findme', email='findme@example.com', user_type='manager',
                    phone='+380661112233', is_active=True)
    manager.set_password('x')
    session.add(manager)
    session.commit()

    found = find_manager_by_phone('+380661112233')
    assert found is not None
    assert found.id == manager.id


def test_find_manager_by_phone_ignores_inactive_or_wrong_role(session):
    from app.telegram_bot.services import find_manager_by_phone

    inactive = User(username='inactive1', email='inactive1@example.com', user_type='manager',
                     phone='+380662223344', is_active=False)
    inactive.set_password('x')
    florist = User(username='florist1', email='florist1@example.com', user_type='florist',
                    phone='+380663334455', is_active=True)
    florist.set_password('x')
    session.add_all([inactive, florist])
    session.commit()

    assert find_manager_by_phone('+380662223344') is None
    assert find_manager_by_phone('+380663334455') is None
    assert find_manager_by_phone('+380000000000') is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_telegram_manager_matching.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_manager_by_phone'`

- [ ] **Step 3: Add `find_manager_by_phone`**

In `app/telegram_bot/services.py`, add near the top of the file (after the existing imports, before the `TelegramService` class):

```python
from app.models.user import User


def find_manager_by_phone(phone: str):
    """Find an active admin/manager User by phone, for Telegram registration."""
    return User.query.filter(
        User.phone == phone,
        User.user_type.in_(('admin', 'manager')),
        User.is_active.is_(True),
    ).first()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_telegram_manager_matching.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire into `register_command`**

In `app/telegram_bot/handlers.py`, replace:

```python
        # Find courier by phone
        courier = Courier.query.filter_by(phone=phone).first()
        
        if not courier:
            await update.message.reply_text(
                "❌ **Кур'єра з таким номером не знайдено в системі.**\n\n"
                "🔍 **Можливі причини:**\n"
                "• Номер введено неправильно\n"
                "• Адміністратор ще не створив ваш акаунт\n"
                "• Номер не відповідає тому, що в системі\n\n"
                "📞 **Зверніться до адміністратора:**\n"
                "• Для створення акаунту кур'єра\n"
                "• Для перевірки правильності номера\n\n"
                "💡 Після створення акаунту спробуйте реєстрацію знову.",
                parse_mode='Markdown'
            )
            return
```

with:

```python
        # Find courier by phone
        courier = Courier.query.filter_by(phone=phone).first()

        if not courier:
            manager = find_manager_by_phone(phone)
            if manager:
                if manager.telegram_chat_id and manager.telegram_chat_id != chat_id:
                    await update.message.reply_text(
                        "❌ **Цей акаунт вже прив'язаний до іншого Telegram.**\n\n"
                        "Зверніться до адміністратора для скидання прив'язки.",
                        parse_mode='Markdown'
                    )
                    return

                manager.telegram_chat_id = chat_id
                manager.telegram_username = user.username if user.username else None
                manager.telegram_registered = True
                manager.last_telegram_activity = datetime.utcnow()
                db.session.commit()

                await update.message.reply_text(
                    f"✅ Реєстрація успішна, {manager.display_name or manager.username}!\n\n"
                    f"Ви отримуватимете сповіщення про нові заявки з сайту.",
                    parse_mode='Markdown'
                )
                logger.info(f"Manager {manager.username} (ID: {manager.id}) successfully registered with Telegram chat_id {chat_id}")
                return

            await update.message.reply_text(
                "❌ **Кур'єра з таким номером не знайдено в системі.**\n\n"
                "🔍 **Можливі причини:**\n"
                "• Номер введено неправильно\n"
                "• Адміністратор ще не створив ваш акаунт\n"
                "• Номер не відповідає тому, що в системі\n\n"
                "📞 **Зверніться до адміністратора:**\n"
                "• Для створення акаунту кур'єра\n"
                "• Для перевірки правильності номера\n\n"
                "💡 Після створення акаунту спробуйте реєстрацію знову.",
                parse_mode='Markdown'
            )
            return
```

- [ ] **Step 6: Wire into `handle_contact`**

In the same file, replace:

```python
        courier = Courier.query.filter_by(phone=phone).first()

        if not courier:
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Поділитися номером телефону", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await update.message.reply_text(
                f"❌ Номер <b>{phone}</b> не знайдено в системі.\n\n"
                "Переконайтеся, що адміністратор додав вас до CRM з саме цим номером.",
                parse_mode='HTML',
                reply_markup=keyboard,
            )
            return
```

with:

```python
        courier = Courier.query.filter_by(phone=phone).first()

        if not courier:
            manager = find_manager_by_phone(phone)
            if manager:
                if manager.telegram_chat_id and manager.telegram_chat_id != chat_id:
                    await update.message.reply_text(
                        "❌ Цей акаунт вже прив'язаний до іншого Telegram.\n"
                        "Зверніться до адміністратора для скидання прив'язки.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return

                manager.telegram_chat_id = chat_id
                manager.telegram_username = user.username if user.username else None
                manager.telegram_registered = True
                manager.last_telegram_activity = datetime.utcnow()
                db.session.commit()

                await update.message.reply_text(
                    f"✅ Реєстрація успішна, {manager.display_name or manager.username}!\n\n"
                    "Ви отримуватимете сповіщення про нові заявки з сайту.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                logger.info(f"Manager {manager.username} (ID: {manager.id}) registered via contact sharing, chat_id={chat_id}")
                return

            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Поділитися номером телефону", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await update.message.reply_text(
                f"❌ Номер <b>{phone}</b> не знайдено в системі.\n\n"
                "Переконайтеся, що адміністратор додав вас до CRM з саме цим номером.",
                parse_mode='HTML',
                reply_markup=keyboard,
            )
            return
```

- [ ] **Step 7: Add the import**

At the top of `app/telegram_bot/handlers.py`, add to the existing `from .services import TelegramService` line's neighborhood:

```python
from .services import TelegramService, find_manager_by_phone
```

- [ ] **Step 8: Run tests to verify nothing broke**

Run: `pytest tests/unit/test_telegram_manager_matching.py -v`
Expected: PASS. There are no pre-existing automated tests for `handlers.py` in this codebase (confirmed during research) — the handler-body edits in Steps 5-6 are verified by careful code review against the exact before/after blocks above, not by an automated handler test, consistent with this codebase's existing testing coverage for this file.

- [ ] **Step 9: Commit**

```bash
git add app/telegram_bot/services.py app/telegram_bot/handlers.py \
        tests/unit/test_telegram_manager_matching.py
git commit -m "feat: let admin/manager Users register Telegram via the courier bot flow"
```

---

### Task 7: Settings → Users: phone field, Telegram status, reset action

**Files:**
- Modify: `app/blueprints/settings/routes.py`
- Modify: `app/templates/settings/users.html`
- Test: `tests/unit/test_settings_users_telegram.py`

**Interfaces:**
- Produces: `POST /settings/users/<int:user_id>/reset-telegram` (endpoint `settings.reset_user_telegram`).
- Modifies: `create_user`, `update_user`, `get_users` to read/write `User.phone`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_settings_users_telegram.py
import json

from app.models.user import User


def _login(app, client, user):
    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user.id)
        flask_session['_fresh'] = True


def _make_admin(session):
    admin = User(username='admin_settings', email='admin_settings@example.com',
                 user_type='admin', is_active=True)
    admin.set_password('secret')
    session.add(admin)
    session.commit()
    return admin


def test_create_user_accepts_and_normalizes_phone(app, session):
    admin = _make_admin(session)
    client = app.test_client()
    _login(app, client, admin)

    resp = client.post('/settings/users', data=json.dumps({
        'username': 'newmgr', 'display_name': 'New Manager', 'role': 'manager',
        'password': 'secretpw', 'password_confirm': 'secretpw',
        'phone': '0501234567',
    }), content_type='application/json')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    created = User.query.filter_by(username='newmgr').first()
    assert created.phone == '+380501234567'


def test_create_user_rejects_duplicate_phone(app, session):
    admin = _make_admin(session)
    existing = User(username='existingmgr', email='existingmgr@example.com',
                     user_type='manager', phone='+380501234567')
    existing.set_password('x')
    session.add(existing)
    session.commit()

    client = app.test_client()
    _login(app, client, admin)

    resp = client.post('/settings/users', data=json.dumps({
        'username': 'dupmgr', 'role': 'manager',
        'password': 'secretpw', 'password_confirm': 'secretpw',
        'phone': '+380501234567',
    }), content_type='application/json')

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['success'] is False


def test_get_users_includes_telegram_fields(app, session):
    admin = _make_admin(session)
    mgr = User(username='tgmgr', email='tgmgr@example.com', user_type='manager',
               phone='+380509998877', telegram_chat_id=12345, telegram_registered=True,
               telegram_username='tguser')
    mgr.set_password('x')
    session.add(mgr)
    session.commit()

    client = app.test_client()
    _login(app, client, admin)
    resp = client.get('/settings/users/list')

    assert resp.status_code == 200
    body = resp.get_json()
    row = next(u for u in body if u['username'] == 'tgmgr')
    assert row['phone'] == '+380509998877'
    assert row['telegram_registered'] is True
    assert row['telegram_username'] == 'tguser'


def test_reset_user_telegram_clears_fields(app, session):
    admin = _make_admin(session)
    mgr = User(username='resetmgr', email='resetmgr@example.com', user_type='manager',
               telegram_chat_id=99999, telegram_registered=True, telegram_username='old')
    mgr.set_password('x')
    session.add(mgr)
    session.commit()

    client = app.test_client()
    _login(app, client, admin)
    resp = client.post(f'/settings/users/{mgr.id}/reset-telegram')

    assert resp.status_code == 200
    updated = User.query.get(mgr.id)
    assert updated.telegram_chat_id is None
    assert updated.telegram_registered is False
    assert updated.telegram_username is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_settings_users_telegram.py -v`
Expected: FAIL — `phone` not accepted/returned yet, `reset-telegram` route 404s.

- [ ] **Step 3: Modify `create_user`**

In `app/blueprints/settings/routes.py`, in `create_user()`, add phone handling. Replace:

```python
    username = (data.get('username') or '').strip()
    display_name = (data.get('display_name') or '').strip() or None
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''
    role_name = (data.get('role') or '').strip()

    errors = []
    if not username:
        errors.append('Логін не може бути порожнім')
    if not password:
        errors.append('Пароль не може бути порожнім')
    elif len(password) < 6:
        errors.append('Пароль має бути не менше 6 символів')
    if password != password_confirm:
        errors.append('Паролі не збігаються')
    if role_name not in ('admin', 'manager', 'florist'):
        errors.append('Роль має бути admin, manager або florist')
    if username and User.query.filter_by(username=username).first():
        errors.append('Користувач з таким логіном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name.capitalize())
        db.session.add(role)
        db.session.flush()

    email = f'{username}@crm.local'
    user = User(username=username, display_name=display_name, email=email, user_type=role_name, is_active=True)
    user.set_password(password)
    user.roles.append(role)
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'user': {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or '',
        'user_type': user.user_type,
        'roles': [role_name],
        'is_active': user.is_active,
    }})
```

with:

```python
    username = (data.get('username') or '').strip()
    display_name = (data.get('display_name') or '').strip() or None
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''
    role_name = (data.get('role') or '').strip()
    phone_raw = (data.get('phone') or '').strip()
    phone = normalize_phone(phone_raw) if phone_raw else None

    errors = []
    if not username:
        errors.append('Логін не може бути порожнім')
    if not password:
        errors.append('Пароль не може бути порожнім')
    elif len(password) < 6:
        errors.append('Пароль має бути не менше 6 символів')
    if password != password_confirm:
        errors.append('Паролі не збігаються')
    if role_name not in ('admin', 'manager', 'florist'):
        errors.append('Роль має бути admin, manager або florist')
    if username and User.query.filter_by(username=username).first():
        errors.append('Користувач з таким логіном вже існує')
    if phone_raw and not phone:
        errors.append('Неправильний формат телефону')
    if phone and User.query.filter_by(phone=phone).first():
        errors.append('Користувач з таким телефоном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name.capitalize())
        db.session.add(role)
        db.session.flush()

    email = f'{username}@crm.local'
    user = User(username=username, display_name=display_name, email=email, user_type=role_name,
                is_active=True, phone=phone)
    user.set_password(password)
    user.roles.append(role)
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'user': {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or '',
        'user_type': user.user_type,
        'roles': [role_name],
        'is_active': user.is_active,
        'phone': user.phone or '',
    }})
```

Add the import at the top of `app/blueprints/settings/routes.py`, alongside the existing imports:

```python
from app.services.csv_import_service import normalize_phone
```

- [ ] **Step 4: Modify `update_user`**

In the same file, in `update_user()`, replace:

```python
    username = (data.get('username') or '').strip()
    display_name = (data.get('display_name') or '').strip() or None
    role_name = (data.get('role') or '').strip()
    password = (data.get('password') or '').strip()
    password_confirm = (data.get('password_confirm') or '').strip()

    errors = []
    if not username:
        errors.append('Логін не може бути порожнім')
    if role_name not in ('admin', 'manager', 'florist'):
        errors.append('Недійсна роль')
    if password and len(password) < 6:
        errors.append('Пароль має бути не менше 6 символів')
    if password and password != password_confirm:
        errors.append('Паролі не збігаються')
    if username and User.query.filter(User.username == username, User.id != user_id).first():
        errors.append('Користувач з таким логіном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    user.username = username
    user.display_name = display_name
    user.user_type = role_name
```

with:

```python
    username = (data.get('username') or '').strip()
    display_name = (data.get('display_name') or '').strip() or None
    role_name = (data.get('role') or '').strip()
    password = (data.get('password') or '').strip()
    password_confirm = (data.get('password_confirm') or '').strip()
    phone_raw = (data.get('phone') or '').strip()
    phone = normalize_phone(phone_raw) if phone_raw else None

    errors = []
    if not username:
        errors.append('Логін не може бути порожнім')
    if role_name not in ('admin', 'manager', 'florist'):
        errors.append('Недійсна роль')
    if password and len(password) < 6:
        errors.append('Пароль має бути не менше 6 символів')
    if password and password != password_confirm:
        errors.append('Паролі не збігаються')
    if username and User.query.filter(User.username == username, User.id != user_id).first():
        errors.append('Користувач з таким логіном вже існує')
    if phone_raw and not phone:
        errors.append('Неправильний формат телефону')
    if phone and User.query.filter(User.phone == phone, User.id != user_id).first():
        errors.append('Користувач з таким телефоном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    user.username = username
    user.display_name = display_name
    user.user_type = role_name
    user.phone = phone
```

And in the same function's JSON response, add `'phone': user.phone or '',` to the returned `'user'` dict (mirroring `create_user`'s response shape).

- [ ] **Step 5: Modify `get_users`**

Replace:

```python
        result.append({
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name or '',
            'user_type': u.user_type,
            'roles': role_names,
            'is_active': u.is_active,
            'is_online': u.is_online,
            'last_seen': u.last_seen.isoformat() if u.last_seen else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
        })
```

with:

```python
        result.append({
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name or '',
            'user_type': u.user_type,
            'roles': role_names,
            'is_active': u.is_active,
            'is_online': u.is_online,
            'last_seen': u.last_seen.isoformat() if u.last_seen else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'phone': u.phone or '',
            'telegram_registered': u.telegram_registered,
            'telegram_username': u.telegram_username or '',
        })
```

- [ ] **Step 6: Add `reset_user_telegram` route**

Add after `change_user_password` (or any existing route in this file — placement doesn't matter functionally):

```python
@bp.route('/settings/users/<int:user_id>/reset-telegram', methods=['POST'])
@login_required
@permission_required('manage_users')
def reset_user_telegram(user_id):
    user = User.query.get_or_404(user_id)
    user.telegram_chat_id = None
    user.telegram_username = None
    user.telegram_registered = False
    user.telegram_notifications_enabled = True
    user.last_telegram_activity = None
    db.session.commit()
    return jsonify({'success': True})
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/test_settings_users_telegram.py -v`
Expected: all 4 tests PASS

- [ ] **Step 8: Update the template**

In `app/templates/settings/users.html`, add a phone input to the create modal. Replace:

```html
          <label class="settings-modal__field">
            <span class="settings-modal__field-label">Роль *</span>
            <select class="settings-modal__input" id="userCreateRole" required>
              <option value="admin">Адміністратор</option>
              <option value="manager">Менеджер</option>
              <option value="florist">Флорист</option>
            </select>
          </label>
```

with:

```html
          <label class="settings-modal__field">
            <span class="settings-modal__field-label">Роль *</span>
            <select class="settings-modal__input" id="userCreateRole" required>
              <option value="admin">Адміністратор</option>
              <option value="manager">Менеджер</option>
              <option value="florist">Флорист</option>
            </select>
          </label>
          <label class="settings-modal__field">
            <span class="settings-modal__field-label">Телефон (для Telegram-сповіщень)</span>
            <input type="text" class="settings-modal__input" id="userCreatePhone" autocomplete="off" placeholder="+380501234567">
          </label>
```

Add the same field to the edit modal. Replace:

```html
          <label class="settings-modal__field">
            <span class="settings-modal__field-label">Роль *</span>
            <select class="settings-modal__input" id="userEditRole" required>
              <option value="admin">Адміністратор</option>
              <option value="manager">Менеджер</option>
              <option value="florist">Флорист</option>
            </select>
          </label>
```

with:

```html
          <label class="settings-modal__field">
            <span class="settings-modal__field-label">Роль *</span>
            <select class="settings-modal__input" id="userEditRole" required>
              <option value="admin">Адміністратор</option>
              <option value="manager">Менеджер</option>
              <option value="florist">Флорист</option>
            </select>
          </label>
          <label class="settings-modal__field">
            <span class="settings-modal__field-label">Телефон (для Telegram-сповіщень)</span>
            <input type="text" class="settings-modal__input" id="userEditPhone" autocomplete="off" placeholder="+380501234567">
          </label>
          <div class="settings-modal__field" id="userEditTelegramStatus" style="font-size:0.85rem;color:#a8a29e;"></div>
```

Add a "Telegram" column to the table header. Replace:

```html
          <tr>
            <th>Логін</th>
            <th>Роль</th>
            <th>Статус</th>
            <th>Онлайн</th>
            <th>Дії</th>
          </tr>
```

with:

```html
          <tr>
            <th>Логін</th>
            <th>Роль</th>
            <th>Статус</th>
            <th>Онлайн</th>
            <th>Telegram</th>
            <th>Дії</th>
          </tr>
```

Update `renderUsers` — the `colspan` values and the new column. Replace:

```javascript
  function renderUsers(users) {
    const tbody = document.getElementById('users-tbody');
    if (!users.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#a8a29e;padding:2rem;">Користувачів ще немає</td></tr>';
      return;
    }
    tbody.innerHTML = users.map(u => `
      <tr data-user-id="${u.id}">
        <td>
          <div class="settings-couriers__name">${u.display_name || u.username}</div>
          ${u.display_name ? `<div style="font-size:0.75rem;color:#a8a29e;">${u.username}</div>` : ''}
        </td>
        <td><span class="settings-couriers__status">${roleLabel(u.user_type)}</span></td>
        <td>
          <span class="settings-couriers__status ${u.is_active ? 'settings-couriers__status--active' : 'settings-couriers__status--inactive'}">
            ${u.is_active ? 'Активний' : 'Неактивний'}
          </span>
        </td>
        <td>${onlineLabel(u)}</td>
        <td>
          <div class="settings-couriers__actions">
            <button class="settings-couriers__action js-user-edit"
                    data-user-id="${u.id}" data-username="${u.username}"
                    data-display-name="${u.display_name || ''}" data-role="${u.user_type}"
                    title="Редагувати">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="settings-couriers__action js-user-toggle"
                    data-user-id="${u.id}"
                    title="${u.is_active ? 'Деактивувати' : 'Активувати'}">
              <i class="bi bi-${u.is_active ? 'pause' : 'play'}"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('');
    bindUserActions();
  }
```

with:

```javascript
  function renderUsers(users) {
    const tbody = document.getElementById('users-tbody');
    if (!users.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#a8a29e;padding:2rem;">Користувачів ще немає</td></tr>';
      return;
    }
    tbody.innerHTML = users.map(u => `
      <tr data-user-id="${u.id}">
        <td>
          <div class="settings-couriers__name">${u.display_name || u.username}</div>
          ${u.display_name ? `<div style="font-size:0.75rem;color:#a8a29e;">${u.username}</div>` : ''}
        </td>
        <td><span class="settings-couriers__status">${roleLabel(u.user_type)}</span></td>
        <td>
          <span class="settings-couriers__status ${u.is_active ? 'settings-couriers__status--active' : 'settings-couriers__status--inactive'}">
            ${u.is_active ? 'Активний' : 'Неактивний'}
          </span>
        </td>
        <td>${onlineLabel(u)}</td>
        <td>
          ${u.telegram_registered
            ? `<span style="display:inline-flex;align-items:center;gap:0.35rem;font-size:0.85rem;">${dot('#22c55e')}@${u.telegram_username || '—'}</span>
               <button class="settings-couriers__action js-user-reset-telegram" data-user-id="${u.id}" title="Скинути Telegram" style="margin-left:0.4rem;">
                 <i class="bi bi-x-circle"></i>
               </button>`
            : `<span style="color:#a8a29e;font-size:0.85rem;">Не прив'язано</span>`}
        </td>
        <td>
          <div class="settings-couriers__actions">
            <button class="settings-couriers__action js-user-edit"
                    data-user-id="${u.id}" data-username="${u.username}"
                    data-display-name="${u.display_name || ''}" data-role="${u.user_type}"
                    data-phone="${u.phone || ''}"
                    data-telegram-registered="${u.telegram_registered}"
                    data-telegram-username="${u.telegram_username || ''}"
                    title="Редагувати">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="settings-couriers__action js-user-toggle"
                    data-user-id="${u.id}"
                    title="${u.is_active ? 'Деактивувати' : 'Активувати'}">
              <i class="bi bi-${u.is_active ? 'pause' : 'play'}"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('');
    bindUserActions();
  }
```

Update `bindUserActions` to populate the phone field on edit, and wire the reset button. Replace:

```javascript
    document.querySelectorAll('.js-user-edit').forEach(btn => {
      btn.addEventListener('click', function() {
        document.getElementById('userEditId').value = this.dataset.userId;
        document.getElementById('userEditUsername').value = this.dataset.username;
        document.getElementById('userEditDisplayName').value = this.dataset.displayName;
        document.getElementById('userEditRole').value = this.dataset.role;
        document.getElementById('userEditPassword').value = '';
        document.getElementById('userEditPasswordConfirm').value = '';
        document.getElementById('userEditError').hidden = true;
        new bootstrap.Modal(document.getElementById('userEditModal')).show();
      });
    });
  }
```

with:

```javascript
    document.querySelectorAll('.js-user-edit').forEach(btn => {
      btn.addEventListener('click', function() {
        document.getElementById('userEditId').value = this.dataset.userId;
        document.getElementById('userEditUsername').value = this.dataset.username;
        document.getElementById('userEditDisplayName').value = this.dataset.displayName;
        document.getElementById('userEditRole').value = this.dataset.role;
        document.getElementById('userEditPhone').value = this.dataset.phone || '';
        document.getElementById('userEditPassword').value = '';
        document.getElementById('userEditPasswordConfirm').value = '';
        document.getElementById('userEditError').hidden = true;
        const statusEl = document.getElementById('userEditTelegramStatus');
        statusEl.textContent = this.dataset.telegramRegistered === 'true'
          ? `Telegram прив'язано: @${this.dataset.telegramUsername || '—'}`
          : "Telegram не прив'язано";
        new bootstrap.Modal(document.getElementById('userEditModal')).show();
      });
    });

    document.querySelectorAll('.js-user-reset-telegram').forEach(btn => {
      btn.addEventListener('click', function() {
        const userId = this.dataset.userId;
        fetch(`/settings/users/${userId}/reset-telegram`, { method: 'POST' })
          .then(r => r.json())
          .then(data => {
            if (data.success) {
              showToast('Telegram-прив\'язку скинуто', 'success');
              loadUsers();
            } else {
              showToast(data.error || 'Помилка', 'error');
            }
          })
          .catch(() => showToast('Помилка мережі', 'error'));
      });
    });
  }
```

Update the create/edit form submit handlers to include `phone`. Replace:

```javascript
    const payload = {
      username: document.getElementById('userCreateUsername').value.trim(),
      display_name: document.getElementById('userCreateDisplayName').value.trim(),
      role: document.getElementById('userCreateRole').value,
      password: document.getElementById('userCreatePassword').value,
      password_confirm: document.getElementById('userCreatePasswordConfirm').value,
    };
```

with:

```javascript
    const payload = {
      username: document.getElementById('userCreateUsername').value.trim(),
      display_name: document.getElementById('userCreateDisplayName').value.trim(),
      role: document.getElementById('userCreateRole').value,
      password: document.getElementById('userCreatePassword').value,
      password_confirm: document.getElementById('userCreatePasswordConfirm').value,
      phone: document.getElementById('userCreatePhone').value.trim(),
    };
```

And replace:

```javascript
    const payload = {
      username: document.getElementById('userEditUsername').value.trim(),
      display_name: document.getElementById('userEditDisplayName').value.trim(),
      role: document.getElementById('userEditRole').value,
      password: document.getElementById('userEditPassword').value,
      password_confirm: document.getElementById('userEditPasswordConfirm').value,
    };
```

with:

```javascript
    const payload = {
      username: document.getElementById('userEditUsername').value.trim(),
      display_name: document.getElementById('userEditDisplayName').value.trim(),
      role: document.getElementById('userEditRole').value,
      password: document.getElementById('userEditPassword').value,
      password_confirm: document.getElementById('userEditPasswordConfirm').value,
      phone: document.getElementById('userEditPhone').value.trim(),
    };
```

Also reset the create form's phone field on successful create. Find `document.getElementById('userCreateForm').reset();` — the native `.reset()` call already clears the new `userCreatePhone` field along with the rest of the form, so no extra change is needed there.

- [ ] **Step 9: Manually verify the template renders**

Run: `python3 -c "
from app import create_app
from app.config import TestingConfig
app = create_app(TestingConfig)
with app.app_context():
    from app.extensions import db
    db.create_all()
    from flask import render_template
    with app.test_request_context('/'):
        html = render_template('settings/users.html')
        assert 'userCreatePhone' in html
        assert 'userEditPhone' in html
        assert 'Telegram' in html
        print('OK')
"`
Expected: prints `OK` with no Jinja errors.

- [ ] **Step 10: Run the full test file plus a full regression pass**

Run: `pytest tests/unit/test_settings_users_telegram.py -v`
Expected: all PASS

Run: `pytest -v`
Expected: all pre-existing tests still PASS (no regressions from the `User` model/route changes).

- [ ] **Step 11: Commit**

```bash
git add app/blueprints/settings/routes.py app/templates/settings/users.html \
        tests/unit/test_settings_users_telegram.py
git commit -m "feat: manage manager Telegram linkage from Settings > Users"
```

---

### Task 8: Full-suite regression check

**Files:** none created; verification only.

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -v`
Expected: all tests PASS, including every new test from Tasks 1-7 and all pre-existing tests (no regressions).

- [ ] **Step 2: Apply the migration locally (only after all commits above are in git)**

```bash
git status
flask db upgrade
```

Expected: `user` gains the 6 new columns and `wix_lead_notification` is created with no errors. If the local dev database has any migration-history drift (as encountered earlier on this branch), resolve it the same way as before — do not force-stamp without understanding the drift; ask before touching a shared dev database's `alembic_version`.

- [ ] **Step 3: Manual smoke test (requires a real Telegram bot token and a running bot process)**

This step needs live infrastructure the automated suite can't cover — note it for the user rather than attempting it as part of the plan:
- Set `CRM_PUBLIC_URL` in `.env` to a real reachable URL (e.g. the same cloudflared tunnel used for the Wix webhook, or a production domain).
- Add a `phone` to an existing admin/manager `User` via `/settings/users`.
- In Telegram, message the bot `/register <that phone>` (or share contact) — confirm the "registration successful" reply and that `/settings/users` now shows the Telegram username with a green dot.
- Send a test Wix webhook (as done earlier in this session) and confirm the registered manager receives a Telegram message with a working "Перейти до замовлення" button.
- Process that lead into an order via the CRM UI, and confirm the same Telegram message gets edited to show the "✅ Оброблено" button pointing at the created order.

- [ ] **Step 4: Commit (only if smoke testing required fixes)**

If Step 3 surfaces bugs, fix them with a normal commit; otherwise this task ends without a commit since no files changed.
