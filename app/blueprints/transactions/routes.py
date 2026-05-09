import io
from datetime import date, datetime
from flask import render_template, request, jsonify, send_file, abort
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from flask_login import login_required, current_user

from app.blueprints.transactions import transactions_bp
from app.extensions import db
from app.models.transaction import Transaction
from app.models.client import Client
from app.models.settings import Settings
from app.models.user import User, Role, user_roles


@transactions_bp.route('/transactions', methods=['GET'])
@login_required
def transactions_list():
    today = date.today()
    default_from = today.replace(day=1).isoformat()
    default_to = today.isoformat()

    date_from_str = request.args.get('date_from', default_from)
    date_to_str = request.args.get('date_to', default_to)

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_from = today.replace(day=1)
        date_from_str = date_from.isoformat()

    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_to = today
        date_to_str = date_to.isoformat()

    client_q = request.args.get('client_q', '').strip().lstrip('@')
    created_by_filter = request.args.get('created_by', '').strip()
    txn_type_filter = request.args.get('txn_type', '').strip()
    account_filter = request.args.get('account', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50

    payment_accounts = Settings.query.filter_by(type='payment_account').order_by(Settings.value).all()

    filtered_query = Transaction.query.filter(
        Transaction.date >= date_from,
        Transaction.date <= date_to,
        Transaction.transaction_type != 'delivery_charge',
    )

    if txn_type_filter in ('debit', 'credit'):
        filtered_query = filtered_query.filter(Transaction.transaction_type == txn_type_filter)

    if account_filter and account_filter.isdigit():
        filtered_query = filtered_query.filter(Transaction.payment_account_id == int(account_filter))

    if client_q:
        filtered_query = (filtered_query
                          .join(Client, Transaction.client_id == Client.id)
                          .filter(or_(
                              Client.instagram.ilike(f'%{client_q}%'),
                              Client.telegram.ilike(f'%{client_q}%'),
                          )))

    if created_by_filter == 'florist':
        florist_ids = (
            db.session.query(User.id)
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .filter(Role.name == 'florist')
            .subquery()
        )
        filtered_query = filtered_query.filter(Transaction.created_by_id.in_(florist_ids))

    pagination = (filtered_query
                  .order_by(Transaction.date.desc(), Transaction.created_at.desc())
                  .paginate(page=page, per_page=per_page, error_out=False))

    all_transactions = Transaction.query.filter(
        Transaction.transaction_type != 'delivery_charge'
    ).all()
    total_balance = sum(
        t.amount if t.transaction_type == 'credit' else -t.amount
        for t in all_transactions
    )

    period_transactions = filtered_query.all()
    period_revenue = sum(t.amount for t in period_transactions if t.transaction_type == 'credit')

    return render_template(
        'transactions/list.html',
        transactions=pagination.items,
        pagination=pagination,
        total_balance=total_balance,
        period_revenue=period_revenue,
        date_from=date_from_str,
        date_to=date_to_str,
        client_q=client_q,
        created_by_filter=created_by_filter,
        txn_type_filter=txn_type_filter,
        account_filter=account_filter,
        payment_accounts=payment_accounts,
    )


@transactions_bp.route('/transactions/export', methods=['GET'])
@login_required
def export_transactions():
    if not (current_user.has_role('admin') or current_user.has_role('manager')):
        abort(403)

    today = date.today()
    date_from_str = request.args.get('date_from', today.replace(day=1).isoformat()).strip()
    date_to_str   = request.args.get('date_to',   today.isoformat()).strip()
    fmt           = request.args.get('format', 'csv').lower()

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_from = today.replace(day=1)
        date_from_str = date_from.isoformat()

    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_to = today
        date_to_str = date_to.isoformat()

    transactions = (
        Transaction.query
        .options(
            joinedload(Transaction.client),
            joinedload(Transaction.created_by),
            joinedload(Transaction.payment_account_setting),
        )
        .filter(
            Transaction.date >= date_from,
            Transaction.date <= date_to,
            Transaction.transaction_type != 'delivery_charge',
        )
        .order_by(Transaction.date.asc(), Transaction.created_at.asc())
        .all()
    )

    headers_row = ['Дата', 'Тип', 'Клієнт', 'Телефон', 'Сума (грн)',
                   'Спосіб оплати', 'Рахунок оплати', 'Тип витрати', 'Коментар', 'Хто вніс']

    def make_row(t):
        creator = t.created_by.display_name if t.created_by and t.created_by.display_name else (
            t.created_by.username if t.created_by else '')
        payment_account = t.payment_account_setting.value if t.payment_account_setting else ''
        return [
            t.date.strftime('%d.%m.%Y'),
            'Поповнення' if t.transaction_type == 'credit' else 'Списання',
            t.client.instagram if t.client else '',
            t.client.phone if t.client and t.client.phone else '',
            t.amount,
            t.payment_type or '',
            payment_account,
            t.expense_type or '',
            t.comment or '',
            creator,
        ]

    filename_base = f'transactions_{date_from_str}_{date_to_str}'

    if fmt == 'xlsx':
        from openpyxl import Workbook
        wb = Workbook(write_only=True)
        ws = wb.create_sheet('Транзакції')
        ws.append(headers_row)
        for t in transactions:
            ws.append(make_row(t))
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{filename_base}.xlsx',
        )

    lines = [','.join('"' + h.replace('"', '""') + '"' for h in headers_row)]
    for t in transactions:
        row = [str(x) for x in make_row(t)]
        lines.append(','.join('"' + x.replace('"', '""') + '"' for x in row))
    csv_bytes = ('﻿' + '\r\n'.join(lines) + '\r\n').encode('utf-8')
    buf = io.BytesIO(csv_bytes)
    return send_file(
        buf,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{filename_base}.csv',
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
                   Client.phone.ilike(f'%{query}%'),
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
    payment_account_id = data.get('payment_account_id')

    if not client_id:
        errors.append('Оберіть клієнта')
    if not amount or int(amount) <= 0:
        errors.append('Введіть суму більше 0')
    if payment_type not in ('monobank', 'cash'):
        errors.append('Оберіть тип оплати')
    if not date_str:
        errors.append('Вкажіть дату')
    if not payment_account_id:
        errors.append('Оберіть рахунок оплати')

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
        payment_account_id=int(payment_account_id),
        date=txn_date,
        created_by_id=current_user.id,
    )
    client.credits = (client.credits or 0) + int(amount)

    db.session.add(txn)
    db.session.commit()

    return jsonify({'success': True, 'id': txn.id})


@transactions_bp.route('/transactions/<int:txn_id>', methods=['GET'])
@login_required
def get_transaction(txn_id):
    if not (current_user.has_role('admin') or current_user.has_role('manager')):
        abort(403)
    txn = Transaction.query.get_or_404(txn_id)
    return jsonify({
        'id': txn.id,
        'transaction_type': txn.transaction_type,
        'amount': txn.amount,
        'payment_type': txn.payment_type,
        'expense_type': txn.expense_type,
        'expense_type_id': txn.expense_type_id,
        'payment_account_id': txn.payment_account_id,
        'comment': txn.comment or '',
        'date': txn.date.isoformat(),
        'client_id': txn.client_id,
        'client_name': txn.client.instagram if txn.client else None,
    })


@transactions_bp.route('/transactions/<int:txn_id>', methods=['PUT'])
@login_required
def update_transaction(txn_id):
    if not (current_user.has_role('admin') or current_user.has_role('manager')):
        abort(403)

    txn = Transaction.query.get_or_404(txn_id)
    data = request.get_json()
    errors = []

    amount = data.get('amount')
    date_str = data.get('date')

    if not amount or int(amount) <= 0:
        errors.append('Введіть суму більше 0')
    if not date_str:
        errors.append('Вкажіть дату')

    payment_account_id = data.get('payment_account_id')
    if not payment_account_id:
        errors.append('Оберіть рахунок оплати')

    if txn.transaction_type == 'credit':
        payment_type = data.get('payment_type')
        if payment_type not in ('monobank', 'cash'):
            errors.append('Оберіть тип оплати')
    else:
        expense_type = data.get('expense_type', '').strip()
        if not expense_type:
            errors.append('Вкажіть тип витрати')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    try:
        txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'errors': ['Невірний формат дати']}), 400

    new_amount = int(amount)

    if txn.transaction_type == 'credit' and txn.client:
        delta = new_amount - txn.amount
        txn.client.credits = (txn.client.credits or 0) + delta

    txn.amount = new_amount
    txn.date = txn_date
    txn.comment = data.get('comment', '').strip() or None
    txn.payment_account_id = int(payment_account_id)

    if txn.transaction_type == 'credit':
        txn.payment_type = data.get('payment_type')
    else:
        txn.expense_type = data.get('expense_type', '').strip()
        expense_type_id = data.get('expense_type_id')
        txn.expense_type_id = int(expense_type_id) if expense_type_id else None

    db.session.commit()
    return jsonify({'success': True})


@transactions_bp.route('/transactions/writeoff', methods=['POST'])
@login_required
def create_writeoff():
    data = request.get_json()
    errors = []

    amount = data.get('amount')
    expense_type = data.get('expense_type', '').strip()
    comment = data.get('comment', '').strip()
    date_str = data.get('date')
    payment_account_id = data.get('payment_account_id')

    if not amount or int(amount) <= 0:
        errors.append('Введіть суму більше 0')
    if not expense_type:
        errors.append('Вкажіть тип витрати')
    if not date_str:
        errors.append('Вкажіть дату')
    if not payment_account_id:
        errors.append('Оберіть рахунок оплати')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    try:
        txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'errors': ['Невірний формат дати']}), 400

    expense_type_id = data.get('expense_type_id')
    txn = Transaction(
        transaction_type='debit',
        client_id=None,
        amount=int(amount),
        expense_type=expense_type,
        expense_type_id=int(expense_type_id) if expense_type_id else None,
        payment_account_id=int(payment_account_id),
        comment=comment or None,
        date=txn_date,
        created_by_id=current_user.id,
    )

    db.session.add(txn)
    db.session.commit()

    return jsonify({'success': True, 'id': txn.id})
