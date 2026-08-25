from decimal import Decimal

from app.extensions import db
from app.models.transaction import Transaction


class TransactionValidationError(ValueError):
    def __init__(self, errors):
        super().__init__('; '.join(errors))
        self.errors = errors


def _parse_amount(amount):
    try:
        return round(float(str(amount).replace(',', '.')), 2)
    except (ValueError, TypeError):
        return 0


def delete_transaction(txn):
    if txn.transaction_type == 'credit' and txn.client:
        txn.client.credits = (txn.client.credits or Decimal(0)) - (txn.amount or Decimal(0))

    db.session.delete(txn)
    db.session.commit()


def create_transfer(*, amount, txn_date, source_account_id, target_account_id, comment, created_by_id):
    errors = []

    amount_val = _parse_amount(amount)
    if amount_val <= 0:
        errors.append('Введіть суму більше 0')
    if not source_account_id:
        errors.append('Оберіть рахунок-джерело')
    if not target_account_id:
        errors.append('Оберіть рахунок-призначення')
    if source_account_id and target_account_id and int(source_account_id) == int(target_account_id):
        errors.append('Рахунок-джерело і рахунок-призначення мають відрізнятись')
    if not txn_date:
        errors.append('Вкажіть дату')

    if errors:
        raise TransactionValidationError(errors)

    txn = Transaction(
        transaction_type='transfer',
        amount=amount_val,
        payment_account_id=int(source_account_id),
        target_payment_account_id=int(target_account_id),
        comment=comment or None,
        date=txn_date,
        created_by_id=created_by_id,
    )
    db.session.add(txn)
    db.session.commit()
    return txn


def update_transfer(txn, *, amount, txn_date, source_account_id, target_account_id, comment):
    errors = []

    amount_val = _parse_amount(amount)
    if amount_val <= 0:
        errors.append('Введіть суму більше 0')
    if not source_account_id:
        errors.append('Оберіть рахунок-джерело')
    if not target_account_id:
        errors.append('Оберіть рахунок-призначення')
    if source_account_id and target_account_id and int(source_account_id) == int(target_account_id):
        errors.append('Рахунок-джерело і рахунок-призначення мають відрізнятись')
    if not txn_date:
        errors.append('Вкажіть дату')

    if errors:
        raise TransactionValidationError(errors)

    txn.amount = amount_val
    txn.date = txn_date
    txn.payment_account_id = int(source_account_id)
    txn.target_payment_account_id = int(target_account_id)
    txn.comment = comment or None
    db.session.commit()
    return txn
