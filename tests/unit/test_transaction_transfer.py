"""
Tests for card-to-card transfer logic (Transaction.transaction_type == 'transfer')

Covers:
- create_transfer creates a transfer transaction with source/target accounts
- create_transfer validation errors (same account, zero amount, missing account)
- update_transfer updates amount/date/accounts/comment
"""
import datetime
import pytest
from app.models.settings import Settings
from app.models.transaction import Transaction
from app.services.transaction_service import (
    TransactionValidationError,
    create_transfer,
    update_transfer,
)


def _make_account(session, value):
    acc = Settings(type='payment_account', value=value)
    session.add(acc)
    session.commit()
    return acc


def test_create_transfer_success(session):
    source = _make_account(session, 'Monobank')
    target = _make_account(session, 'Готівка')

    txn = create_transfer(
        amount='150.50',
        txn_date=datetime.date.today(),
        source_account_id=source.id,
        target_account_id=target.id,
        comment='Поповнення готівкового рахунку',
        created_by_id=None,
    )

    assert txn.id is not None
    assert txn.transaction_type == 'transfer'
    assert float(txn.amount) == 150.50
    assert txn.payment_account_id == source.id
    assert txn.target_payment_account_id == target.id
    assert txn.client_id is None


def test_create_transfer_same_account_rejected(session):
    source = _make_account(session, 'Monobank')

    with pytest.raises(TransactionValidationError):
        create_transfer(
            amount='100',
            txn_date=datetime.date.today(),
            source_account_id=source.id,
            target_account_id=source.id,
            comment='',
            created_by_id=None,
        )


def test_create_transfer_zero_amount_rejected(session):
    source = _make_account(session, 'Monobank')
    target = _make_account(session, 'Готівка')

    with pytest.raises(TransactionValidationError):
        create_transfer(
            amount='0',
            txn_date=datetime.date.today(),
            source_account_id=source.id,
            target_account_id=target.id,
            comment='',
            created_by_id=None,
        )


def test_create_transfer_missing_account_rejected(session):
    target = _make_account(session, 'Готівка')

    with pytest.raises(TransactionValidationError):
        create_transfer(
            amount='100',
            txn_date=datetime.date.today(),
            source_account_id=None,
            target_account_id=target.id,
            comment='',
            created_by_id=None,
        )


def test_update_transfer_changes_fields(session):
    source = _make_account(session, 'Monobank')
    target = _make_account(session, 'Готівка')
    other = _make_account(session, 'ПриватБанк')

    txn = create_transfer(
        amount='100',
        txn_date=datetime.date.today(),
        source_account_id=source.id,
        target_account_id=target.id,
        comment='',
        created_by_id=None,
    )

    new_date = datetime.date.today() - datetime.timedelta(days=1)
    update_transfer(
        txn,
        amount='250',
        txn_date=new_date,
        source_account_id=target.id,
        target_account_id=other.id,
        comment='Виправлено',
    )

    assert float(txn.amount) == 250
    assert txn.date == new_date
    assert txn.payment_account_id == target.id
    assert txn.target_payment_account_id == other.id
    assert txn.comment == 'Виправлено'
