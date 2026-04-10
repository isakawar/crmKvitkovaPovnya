import datetime

from app.models import Client
from app.models.user import User
from app.services.subscription_service import create_draft_subscription


def _make_client(session, instagram, phone=None):
    client = Client(instagram=instagram, phone=phone)
    session.add(client)
    session.commit()
    return client


def test_dashboard_shows_only_due_draft_reminders(app, session):
    due_client = _make_client(session, 'due_draft', '+380991112233')
    future_client = _make_client(session, 'future_draft', '+380994445566')
    today = datetime.date.today()
    manager = User(
        email='manager@example.com',
        username='manager',
        user_type='manager',
        is_active=True,
    )
    manager.set_password('secret')
    session.add(manager)
    session.commit()

    due_sub = create_draft_subscription(
        due_client,
        today - datetime.timedelta(days=1),
        draft_comment='Передзвонити сьогодні',
        draft_bank_link='https://send.monobank.ua/test',
    )
    create_draft_subscription(future_client, today + datetime.timedelta(days=3))

    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(manager.id)
        flask_session['_fresh'] = True

    response = client.get('/dashboard')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Фокус менеджера на сьогодні" in html
    assert "Кому потрібно написати або подзвонити" in html
    assert "Кого потрібно продовжити" in html
    assert 'due_draft' in html
    assert 'future_draft' not in html
    assert f'data-draft-edit="{due_sub.id}"' in html
    assert f'data-draft-convert="{due_sub.id}"' in html
