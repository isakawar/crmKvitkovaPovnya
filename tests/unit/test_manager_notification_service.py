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
