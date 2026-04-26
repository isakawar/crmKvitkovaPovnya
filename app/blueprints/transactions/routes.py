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
    page = request.args.get('page', 1, type=int)
    per_page = 50

    filtered_query = Transaction.query.filter(
        Transaction.date >= date_from,
        Transaction.date <= date_to,
    )

    if client_q:
        filtered_query = (filtered_query
                          .join(Client, Transaction.client_id == Client.id)
                          .filter(or_(
                              Client.instagram.ilike(f'%{client_q}%'),
                              Client.telegram.ilike(f'%{client_q}%'),
                          )))

    pagination = (filtered_query
                  .order_by(Transaction.date.desc(), Transaction.created_at.desc())
                  .paginate(page=page, per_page=per_page, error_out=False))

    all_transactions = Transaction.query.all()
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
        .options(joinedload(Transaction.client))
        .filter(Transaction.date >= date_from, Transaction.date <= date_to)
        .order_by(Transaction.date.asc(), Transaction.created_at.asc())
        .all()
    )

    headers_row = ['Дата', 'Тип', 'Клієнт', 'Телефон', 'Сума (грн)',
                   'Спосіб оплати', 'Тип витрати', 'Коментар', 'Записано']

    def make_row(t):
        kyiv_offset = 3
        created = (t.created_at.replace(tzinfo=None) if t.created_at else None)
        if created:
            from datetime import timedelta
            created_str = (created + timedelta(hours=kyiv_offset)).strftime('%d.%m.%Y %H:%M')
        else:
            created_str = ''
        return [
            t.date.strftime('%d.%m.%Y'),
            'Поповнення' if t.transaction_type == 'credit' else 'Списання',
            t.client.instagram if t.client else '',
            t.client.phone if t.client and t.client.phone else '',
            t.amount,
            t.payment_type or '',
            t.expense_type or '',
            t.comment or '',
            created_str,
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
