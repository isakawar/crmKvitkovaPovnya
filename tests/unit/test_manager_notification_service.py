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
