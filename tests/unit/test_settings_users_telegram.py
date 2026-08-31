import json

from app.models.user import User, Role


def _login(app, client, user):
    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user.id)
        flask_session['_fresh'] = True


def _make_admin(session):
    admin = User(username='admin_settings', email='admin_settings@example.com',
                 user_type='admin', is_active=True)
    admin.set_password('secret')
    role = Role.query.filter_by(name='admin').first()
    if not role:
        role = Role(name='admin', description='Admin')
        session.add(role)
    admin.roles.append(role)
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
