"""
Tests for transaction ↔ order/subscription linking (July 2026 feature).

Covers:
- GET /transactions/clients/<id>/orders: subscriptions collapse to one entry,
  amount fallback chain (charged_amount -> custom_amount -> calculated price)
- POST /transactions/create: order_id -> subscription_id derivation, cross-client
  rejection, unlinked transactions
- PUT /transactions/<id>: relinking on edit, and the asymmetric order_id/
  subscription_id resolution between create and update
"""
import datetime
import pytest
from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.settings import Settings
from app.models.user import User
from app.extensions import db


def _make_client(session, instagram='tx_link_client'):
    c = Client(instagram=instagram)
    session.add(c)
    session.commit()
    return c


def _make_manager(session, username='tx_manager'):
    u = User(email=f'{username}@example.com', username=username, user_type='manager', is_active=True)
    u.set_password('secret')
    session.add(u)
    session.commit()
    from app.models.user import Role
    role = Role.query.filter_by(name='manager').first()
    if not role:
        role = Role(name='manager', description='Manager')
        session.add(role)
        session.commit()
    u.roles.append(role)
    session.commit()
    return u


def _make_payment_account(session, value='Monobank'):
    s = Settings(type='payment_account', value=value)
    session.add(s)
    session.commit()
    return s


def _login(flask_client, user):
    with flask_client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user.id)
        flask_session['_fresh'] = True


def _make_subscription_with_orders(session, client, n=4, charged_amount=200):
    sub = Subscription(
        client_id=client.id,
        type='Weekly',
        status='active',
        delivery_day='ПН',
        recipient_name='Отримувач',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        size='M',
        for_whom='Дружина',
    )
    session.add(sub)
    session.flush()

    today = datetime.date.today()
    orders = []
    for i in range(n):
        o = Order(
            client_id=client.id,
            subscription_id=sub.id,
            sequence_number=i + 1,
            recipient_name='Отримувач',
            recipient_phone='+380991234567',
            city='Київ',
            street='Хрещатик 1',
            is_pickup=False,
            delivery_method='courier',
            size='M',
            delivery_date=today + datetime.timedelta(days=7 * i),
            for_whom='Дружина',
            charged_amount=charged_amount,
        )
        session.add(o)
        session.flush()
        d = Delivery(
            order_id=o.id,
            client_id=client.id,
            delivery_date=o.delivery_date,
            status='Очікує',
            size='M',
            phone='+380991234567',
            delivery_method='courier',
        )
        session.add(d)
        orders.append(o)
    session.commit()
    return sub, orders


def _make_onetime_order(session, client, charged_amount=350):
    today = datetime.date.today()
    o = Order(
        client_id=client.id,
        subscription_id=None,
        recipient_name='Одноразовий',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        is_pickup=False,
        delivery_method='courier',
        size='L',
        delivery_date=today,
        for_whom='Друг',
        charged_amount=charged_amount,
    )
    session.add(o)
    session.commit()
    return o


# ── GET /transactions/clients/<id>/orders ─────────────────────────────────────

def test_client_orders_dedups_subscription_to_one_entry(app, session):
    client = _make_client(session, 'dedup_client')
    sub, orders = _make_subscription_with_orders(session, client, n=4, charged_amount=200)
    onetime = _make_onetime_order(session, client, charged_amount=350)

    flask_client = app.test_client()
    resp = flask_client.get(f'/transactions/clients/{client.id}/orders')
    assert resp.status_code == 200
    data = resp.get_json()

    sub_entries = [row for row in data if row['is_subscription']]
    onetime_entries = [row for row in data if not row['is_subscription']]

    assert len(sub_entries) == 1
    assert sub_entries[0]['subscription_id'] == sub.id
    assert len(sub_entries[0]['subscription']['deliveries']) == 4
    assert len(onetime_entries) == 1
    assert onetime_entries[0]['id'] == onetime.id


def test_client_orders_subscription_amount_is_sum_of_deliveries(app, session):
    client = _make_client(session, 'sum_client')
    sub, orders = _make_subscription_with_orders(session, client, n=4, charged_amount=200)

    flask_client = app.test_client()
    resp = flask_client.get(f'/transactions/clients/{client.id}/orders')
    data = resp.get_json()

    sub_entry = next(row for row in data if row['is_subscription'])
    assert sub_entry['subscription']['total'] == 800  # 4 * 200


def test_client_orders_amount_falls_back_to_custom_amount(app, session):
    client = _make_client(session, 'fallback_client')
    today = datetime.date.today()
    o = Order(
        client_id=client.id,
        recipient_name='Х', recipient_phone='+380991234567',
        city='Київ', street='Вул', is_pickup=False, delivery_method='courier',
        size='Власний', delivery_date=today, for_whom='Я',
        charged_amount=None, custom_amount=777,
    )
    session.add(o)
    session.commit()

    flask_client = app.test_client()
    resp = flask_client.get(f'/transactions/clients/{client.id}/orders')
    data = resp.get_json()

    assert data[0]['amount'] == 777.0


# ── POST /transactions/create ──────────────────────────────────────────────────

def test_create_transaction_links_order_and_derives_subscription(app, session):
    client = _make_client(session, 'create_link_client')
    manager = _make_manager(session, 'create_mgr')
    account = _make_payment_account(session)
    sub, orders = _make_subscription_with_orders(session, client)

    flask_client = app.test_client()
    _login(flask_client, manager)

    resp = flask_client.post('/transactions/create', json={
        'client_id': client.id,
        'amount': 800,
        'payment_type': 'monobank',
        'date': datetime.date.today().isoformat(),
        'payment_account_id': account.id,
        'order_id': orders[0].id,
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True

    txn = Transaction.query.get(body['id'])
    assert txn.order_id == orders[0].id
    assert txn.subscription_id == sub.id


def test_create_transaction_without_order_id_leaves_links_null(app, session):
    client = _make_client(session, 'no_link_client')
    manager = _make_manager(session, 'no_link_mgr')
    account = _make_payment_account(session)

    flask_client = app.test_client()
    _login(flask_client, manager)

    resp = flask_client.post('/transactions/create', json={
        'client_id': client.id,
        'amount': 100,
        'payment_type': 'cash',
        'date': datetime.date.today().isoformat(),
        'payment_account_id': account.id,
    })
    body = resp.get_json()
    txn = Transaction.query.get(body['id'])
    assert txn.order_id is None
    assert txn.subscription_id is None


def test_create_transaction_rejects_order_belonging_to_other_client(app, session):
    client_a = _make_client(session, 'client_a')
    client_b = _make_client(session, 'client_b')
    manager = _make_manager(session, 'cross_mgr')
    account = _make_payment_account(session)
    _sub, orders = _make_subscription_with_orders(session, client_a)

    flask_client = app.test_client()
    _login(flask_client, manager)

    resp = flask_client.post('/transactions/create', json={
        'client_id': client_b.id,
        'amount': 200,
        'payment_type': 'cash',
        'date': datetime.date.today().isoformat(),
        'payment_account_id': account.id,
        'order_id': orders[0].id,
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['success'] is False
    assert 'Замовлення не належить цьому клієнту' in body['errors']
    assert Transaction.query.count() == 0


# ── PUT /transactions/<id> ──────────────────────────────────────────────────────

def test_update_transaction_relinks_to_new_order(app, session):
    client = _make_client(session, 'relink_client')
    manager = _make_manager(session, 'relink_mgr')
    account = _make_payment_account(session)
    sub, orders = _make_subscription_with_orders(session, client)
    onetime = _make_onetime_order(session, client)

    txn = Transaction(
        transaction_type='credit', client_id=client.id, amount=350,
        payment_type='cash', payment_account_id=account.id,
        date=datetime.date.today(), order_id=onetime.id, subscription_id=None,
    )
    session.add(txn)
    session.commit()

    flask_client = app.test_client()
    _login(flask_client, manager)

    resp = flask_client.put(f'/transactions/{txn.id}', json={
        'amount': 800,
        'date': datetime.date.today().isoformat(),
        'payment_account_id': account.id,
        'payment_type': 'monobank',
        'order_id': orders[0].id,
    })
    assert resp.status_code == 200
    session.refresh(txn)
    assert txn.order_id == orders[0].id
    assert txn.subscription_id == sub.id


def test_update_transaction_clearing_order_id_without_subscription_id_unlinks_both(app, session):
    """Regression guard: update_transaction has a second code path (no order_id
    in payload) that reads subscription_id directly from the request instead of
    deriving it from an order, unlike create_transaction. If the client omits
    both, both links must end up null rather than keeping a stale subscription_id."""
    client = _make_client(session, 'unlink_client')
    manager = _make_manager(session, 'unlink_mgr')
    account = _make_payment_account(session)
    sub, orders = _make_subscription_with_orders(session, client)

    txn = Transaction(
        transaction_type='credit', client_id=client.id, amount=800,
        payment_type='monobank', payment_account_id=account.id,
        date=datetime.date.today(), order_id=orders[0].id, subscription_id=sub.id,
    )
    session.add(txn)
    session.commit()

    flask_client = app.test_client()
    _login(flask_client, manager)

    resp = flask_client.put(f'/transactions/{txn.id}', json={
        'amount': 800,
        'date': datetime.date.today().isoformat(),
        'payment_account_id': account.id,
        'payment_type': 'monobank',
        # no order_id, no subscription_id -> should fully unlink
    })
    assert resp.status_code == 200
    session.refresh(txn)
    assert txn.order_id is None
    assert txn.subscription_id is None


def test_update_transaction_requires_manager_or_admin_role(app, session):
    client = _make_client(session, 'role_client')
    florist = User(email='florist@example.com', username='role_florist', user_type='florist', is_active=True)
    florist.set_password('secret')
    session.add(florist)
    session.commit()
    account = _make_payment_account(session)

    txn = Transaction(
        transaction_type='credit', client_id=client.id, amount=100,
        payment_type='cash', payment_account_id=account.id, date=datetime.date.today(),
    )
    session.add(txn)
    session.commit()

    flask_client = app.test_client()
    _login(flask_client, florist)

    resp = flask_client.put(f'/transactions/{txn.id}', json={
        'amount': 100, 'date': datetime.date.today().isoformat(),
        'payment_account_id': account.id, 'payment_type': 'cash',
    })
    assert resp.status_code == 403
