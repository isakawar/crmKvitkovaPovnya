"""
Tests for Transaction model

Covers:
- Transaction creation with credit type
- Transaction creation with debit type
- Transaction date and amount fields
- Transaction client relationship
- Transaction payment_type field
- Transaction expense_type field
"""
import datetime
import pytest
from app.models import Client
from app.models.transaction import Transaction


def _make_client(session, instagram='tx_client'):
    c = Client(instagram=instagram)
    session.add(c)
    session.commit()
    return c


# ── Transaction creation ─────────────────────────────────────────────────────

def test_transaction_credit_default(session):
    client = _make_client(session, 'tx_credit')
    tx = Transaction(
        transaction_type='credit',
        client_id=client.id,
        amount=1000,
        payment_type='monobank',
        date=datetime.date.today(),
    )
    session.add(tx)
    session.commit()

    assert tx.transaction_type == 'credit'
    assert tx.amount == 1000
    assert tx.payment_type == 'monobank'


def test_transaction_debit(session):
    client = _make_client(session, 'tx_debit')
    tx = Transaction(
        transaction_type='debit',
        client_id=client.id,
        amount=500,
        expense_type='courier_payment',
        date=datetime.date.today(),
    )
    session.add(tx)
    session.commit()

    assert tx.transaction_type == 'debit'
    assert tx.amount == 500
    assert tx.expense_type == 'courier_payment'


def test_transaction_cash_payment(session):
    client = _make_client(session, 'tx_cash')
    tx = Transaction(
        transaction_type='credit',
        client_id=client.id,
        amount=200,
        payment_type='cash',
        date=datetime.date.today(),
    )
    session.add(tx)
    session.commit()

    assert tx.payment_type == 'cash'


def test_transaction_without_client(session):
    tx = Transaction(
        transaction_type='debit',
        client_id=None,
        amount=100,
        expense_type='office_supplies',
        date=datetime.date.today(),
    )
    session.add(tx)
    session.commit()

    assert tx.client_id is None


def test_transaction_client_relationship(session):
    client = _make_client(session, 'tx_rel')
    tx = Transaction(
        transaction_type='credit',
        client_id=client.id,
        amount=1500,
        payment_type='monobank',
        date=datetime.date.today(),
    )
    session.add(tx)
    session.commit()

    assert tx.client is not None
    assert tx.client.instagram == 'tx_rel'
    assert client.transactions[0].id == tx.id


def test_transaction_comment_field(session):
    client = _make_client(session, 'tx_comment')
    tx = Transaction(
        transaction_type='credit',
        client_id=client.id,
        amount=300,
        payment_type='monobank',
        date=datetime.date.today(),
        comment='Поповнення за підписку',
    )
    session.add(tx)
    session.commit()

    assert tx.comment == 'Поповнення за підписку'


def test_transaction_created_at_auto_set(session):
    client = _make_client(session, 'tx_ts')
    tx = Transaction(
        transaction_type='credit',
        client_id=client.id,
        amount=100,
        payment_type='cash',
        date=datetime.date.today(),
    )
    session.add(tx)
    session.commit()

    assert tx.created_at is not None
