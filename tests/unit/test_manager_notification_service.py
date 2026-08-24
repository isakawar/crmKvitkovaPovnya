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


def test_webhook_returns_200_when_notification_call_raises(app, session, monkeypatch):
    from tests.unit.test_wix_integration_service import SAMPLE_WIX_PAYLOAD
    import copy

    app.config['WIX_ALLOWED_SITE_IDS'] = '2c31eac1-a4f1-4fd2-886d-361377a42a1f'

    def _boom(lead):
        raise RuntimeError('boom')

    monkeypatch.setattr('app.blueprints.integrations.routes.send_new_lead_notification', _boom)

    client = app.test_client()
    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)

    resp = client.post('/api/integrations/wix/order-placed',
                        data=json.dumps(payload), content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True


def test_mark_lead_processed_completes_when_notify_raises(session, monkeypatch):
    from app.services.wix_integration_service import mark_lead_processed
    from app.models import Client
    from app.models.order import Order
    import datetime as _dt

    def _boom(lead):
        raise RuntimeError('boom')

    monkeypatch.setattr('app.services.wix_integration_service.notify_lead_processed', _boom)

    client_obj = Client(instagram='tguser2')
    lead = _make_lead(session, wix_order_id='order-notify-7')
    session.add(client_obj)
    session.commit()
    order = Order(
        client_id=client_obj.id, recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', delivery_date=_dt.date.today(), for_whom='Дружина',
    )
    session.add(order)
    session.commit()

    manager = User(username='mgr10', email='mgr10@example.com', user_type='manager')
    manager.set_password('x')
    session.add(manager)
    session.commit()

    mark_lead_processed(lead, order, manager)  # must not raise

    assert lead.status == 'processed'
