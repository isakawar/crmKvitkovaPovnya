from decimal import Decimal

from app.extensions import db
from app.constants import TXN_TRANSFER, balance_delta
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


def apply_balance_delta(txn, delta):
    """Змістити ``client.credits`` на ``delta`` з урахуванням типу транзакції.

    Єдина точка, через яку баланс клієнта рухається при редагуванні/видаленні
    транзакцій. Раніше і видалення, і редагування правили ``credits`` лише для
    типу ``credit`` — а в таблиці, крім нього, живуть ``delivery_charge`` і
    ``adjustment``, які на баланс так само впливають. Через це видалення ручного
    коригування (воно видиме у списку транзакцій!) знімало рядок, але лишало
    зсунутий баланс — і, оскільки звіт «Баланс клієнтів» рахує історію назад від
    ``client.credits``, зсув переписував усі попередні місяці.
    """
    if not txn.client or not delta:
        return
    txn.client.credits = (txn.client.credits or Decimal(0)) + delta


def delete_transaction(txn):
    """Видалити транзакцію, повернувши баланс клієнта у стан «ніби її не було»."""
    apply_balance_delta(txn, -balance_delta(txn.transaction_type, txn.amount))

    db.session.delete(txn)
    db.session.commit()


def change_transaction_amount(txn, new_amount):
    """Змінити суму транзакції, підтягнувши баланс клієнта на різницю.

    Працює для будь-якого типу, що впливає на баланс, а не лише для ``credit``.
    """
    old_delta = balance_delta(txn.transaction_type, txn.amount)
    new_delta = balance_delta(txn.transaction_type, Decimal(str(new_amount)))
    apply_balance_delta(txn, new_delta - old_delta)
    txn.amount = new_amount


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
        transaction_type=TXN_TRANSFER,
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
