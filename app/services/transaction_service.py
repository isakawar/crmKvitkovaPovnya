from decimal import Decimal

from app.extensions import db


def delete_transaction(txn):
    if txn.transaction_type == 'credit' and txn.client:
        txn.client.credits = (txn.client.credits or Decimal(0)) - (txn.amount or Decimal(0))

    db.session.delete(txn)
    db.session.commit()
