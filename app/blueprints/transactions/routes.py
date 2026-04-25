from datetime import date, datetime
from flask import render_template, request, jsonify
from sqlalchemy import or_
from flask_login import login_required

from app.blueprints.transactions import transactions_bp
from app.extensions import db
from app.models.transaction import Transaction
from app.models.client import Client


@transactions_bp.route('/transactions', methods=['GET'])
@login_required
def transactions_list():
    transactions = (Transaction.query
                    .order_by(Transaction.date.desc(), Transaction.created_at.desc())
                    .all())

    total_balance = sum(
        t.amount if t.transaction_type == 'credit' else -t.amount
        for t in transactions
    )

    today = date.today()
    monthly_revenue = sum(
        t.amount for t in transactions
        if t.transaction_type == 'credit'
        and t.date.year == today.year and t.date.month == today.month
    )

    return render_template(
        'transactions/list.html',
        transactions=transactions,
        total_balance=total_balance,
        monthly_revenue=monthly_revenue,
        current_month=today.strftime('%B %Y'),
    )


@transactions_bp.route('/transactions/clients/search', methods=['GET'])
@login_required
def search_clients():
    query = request.args.get('q', '').strip().lstrip('@')
    if not query:
        return jsonify([])
    clients = (Client.query
               .filter(or_(
                   Client.instagram.ilike(f'%{query}%'),
                   Client.telegram.ilike(f'%{query}%'),
               ))
               .order_by(Client.instagram.nullslast(), Client.telegram)
               .limit(10)
               .all())
    return jsonify([{'id': c.id, 'instagram': c.instagram, 'telegram': c.telegram, 'phone': c.phone or ''} for c in clients])


@transactions_bp.route('/transactions/create', methods=['POST'])
@login_required
def create_transaction():
    data = request.get_json()
    errors = []

    client_id = data.get('client_id')
    amount = data.get('amount')
    payment_type = data.get('payment_type')
    date_str = data.get('date')

    if not client_id:
        errors.append('Оберіть клієнта')
    if not amount or int(amount) <= 0:
        errors.append('Введіть суму більше 0')
    if payment_type not in ('monobank', 'cash'):
        errors.append('Оберіть тип оплати')
    if not date_str:
        errors.append('Вкажіть дату')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    client = Client.query.get(int(client_id))
    if not client:
        return jsonify({'success': False, 'errors': ['Клієнта не знайдено']}), 400

    try:
        txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'errors': ['Невірний формат дати']}), 400

    txn = Transaction(
        transaction_type='credit',
        client_id=client.id,
        amount=int(amount),
        payment_type=payment_type,
        date=txn_date,
    )
    client.credits = (client.credits or 0) + int(amount)

    db.session.add(txn)
    db.session.commit()

    return jsonify({'success': True, 'id': txn.id})


@transactions_bp.route('/transactions/writeoff', methods=['POST'])
@login_required
def create_writeoff():
    data = request.get_json()
    errors = []

    amount = data.get('amount')
    expense_type = data.get('expense_type', '').strip()
    comment = data.get('comment', '').strip()
    date_str = data.get('date')

    if not amount or int(amount) <= 0:
        errors.append('Введіть суму більше 0')
    if not expense_type:
        errors.append('Вкажіть тип витрати')
    if not date_str:
        errors.append('Вкажіть дату')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    try:
        txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'errors': ['Невірний формат дати']}), 400

    txn = Transaction(
        transaction_type='debit',
        client_id=None,
        amount=int(amount),
        expense_type=expense_type,
        comment=comment or None,
        date=txn_date,
    )

    db.session.add(txn)
    db.session.commit()

    return jsonify({'success': True, 'id': txn.id})
