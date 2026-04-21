from datetime import date

from flask import render_template, request, jsonify
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.blueprints.certificates import certificates_bp
from app.extensions import db
from app.models.certificate import Certificate, generate_certificate_code
from app.models.order import Order



@certificates_bp.route('/certificates', methods=['GET'])
@login_required
def certificates_list():
    status_filter = request.args.get('status', 'all')

    query = Certificate.query.order_by(Certificate.created_at.desc())

    today = date.today()

    if status_filter == 'active':
        query = query.filter(Certificate.status == 'active', Certificate.expires_at >= today)
    elif status_filter == 'used':
        query = query.filter(Certificate.status == 'used')
    elif status_filter == 'expired':
        query = query.filter(
            (Certificate.status == 'expired') |
            ((Certificate.status == 'active') & (Certificate.expires_at < today))
        )

    certificates = query.options(
        joinedload(Certificate.order).joinedload(Order.client)
    ).all()

    counts = {
        'all': Certificate.query.count(),
        'active': Certificate.query.filter(Certificate.status == 'active', Certificate.expires_at >= today).count(),
        'used': Certificate.query.filter(Certificate.status == 'used').count(),
        'expired': Certificate.query.filter(
            (Certificate.status == 'expired') |
            ((Certificate.status == 'active') & (Certificate.expires_at < today))
        ).count(),
    }

    return render_template(
        'certificates/list.html',
        certificates=certificates,
        status_filter=status_filter,
        counts=counts,
    )


@certificates_bp.route('/certificates/generate-code', methods=['GET'])
@login_required
def generate_code():
    cert_type = request.args.get('type', 'amount')
    code = generate_certificate_code(cert_type)
    # Ensure uniqueness (collision extremely unlikely but safe)
    while Certificate.query.filter_by(code=code).first():
        existing = Certificate.query.filter_by(code=code).first()
        num = int(existing.code[1:]) + 1
        prefix = code[0]
        code = f'{prefix}{num:04d}'
    return jsonify({'code': code})


@certificates_bp.route('/certificates/create', methods=['POST'])
@login_required
def create_certificate():
    data = request.get_json()

    cert_type = data.get('type')
    code = (data.get('code') or '').strip()
    comment = data.get('comment', '').strip() or None

    errors = []
    if cert_type not in ('amount', 'size', 'subscription'):
        errors.append('Невірний тип сертифіката')

    if not code:
        errors.append('Код сертифіката обов\'язковий')
    elif Certificate.query.filter_by(code=code).first():
        errors.append('Сертифікат з таким кодом вже існує')

    value_amount = None
    value_size = None

    if cert_type == 'amount':
        try:
            value_amount = float(data.get('value_amount') or 0)
            if value_amount <= 0:
                errors.append('Сума повинна бути більше 0')
        except (ValueError, TypeError):
            errors.append('Невірна сума')

    elif cert_type == 'size':
        value_size = data.get('value_size')
        if not value_size:
            errors.append('Розмір обов\'язковий')

    elif cert_type == 'subscription':
        value_size = data.get('value_size')
        if not value_size:
            errors.append('Розмір обов\'язковий')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    today = date.today()
    expires_at = date(today.year + 1, today.month, today.day)

    cert = Certificate(
        code=code,
        type=cert_type,
        value_amount=value_amount,
        value_size=value_size,
        expires_at=expires_at,
        comment=comment,
        created_by_user_id=current_user.id,
    )
    db.session.add(cert)
    db.session.commit()

    return jsonify({'success': True, 'id': cert.id})


@certificates_bp.route('/certificates/<int:cert_id>/detail', methods=['GET'])
@login_required
def certificate_detail(cert_id):
    cert = Certificate.query.get_or_404(cert_id)

    order_info = None
    if cert.order_id and cert.order:
        order = cert.order
        is_subscription = order.subscription_id is not None
        delivery_type = order.subscription.type if order.subscription else 'One-time'
        client_name = None
        if order.client:
            client_name = order.client.instagram or f'#{order.client.id}'
        order_info = {
            'id': order.id,
            'is_subscription': is_subscription,
            'delivery_type': delivery_type,
            'client_name': client_name,
        }

    return jsonify({
        'id': cert.id,
        'code': cert.code,
        'type': cert.type,
        'type_display': cert.type_display(),
        'value_display': cert.value_display(),
        'value_amount': float(cert.value_amount) if cert.value_amount else None,
        'value_size': cert.value_size,
        'status': cert.effective_status(),
        'status_display': cert.status_display(),
        'expires_at': cert.expires_at.strftime('%d.%m.%Y'),
        'comment': cert.comment or '',
        'created_at': cert.created_at.strftime('%d.%m.%Y %H:%M') if cert.created_at else None,
        'created_by': cert.created_by.username if cert.created_by else None,
        'used_at': cert.used_at.strftime('%d.%m.%Y %H:%M') if cert.used_at else None,
        'order': order_info,
    })


@certificates_bp.route('/certificates/<int:cert_id>/update', methods=['POST'])
@login_required
def update_certificate(cert_id):
    cert = Certificate.query.get_or_404(cert_id)

    if cert.status == 'used':
        return jsonify({'success': False, 'errors': ['Використаний сертифікат не можна редагувати']}), 400

    data = request.get_json()
    cert_type = data.get('type')
    comment = data.get('comment', '').strip() or None

    errors = []
    if cert_type not in ('amount', 'size', 'subscription'):
        errors.append('Невірний тип сертифіката')

    value_amount = None
    value_size = None

    if cert_type == 'amount':
        try:
            value_amount = float(data.get('value_amount') or 0)
            if value_amount <= 0:
                errors.append('Сума повинна бути більше 0')
        except (ValueError, TypeError):
            errors.append('Невірна сума')
    elif cert_type in ('size', 'subscription'):
        value_size = data.get('value_size')
        if not value_size:
            errors.append('Розмір обов\'язковий')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    cert.type = cert_type
    cert.value_amount = value_amount
    cert.value_size = value_size
    cert.comment = comment
    db.session.commit()

    return jsonify({'success': True})


@certificates_bp.route('/certificates/validate', methods=['POST'])
@login_required
def validate_certificate():
    data = request.get_json()
    code = (data.get('code') or '').strip()

    if not code:
        return jsonify({'valid': False, 'error': 'Введіть код сертифіката'})

    cert = Certificate.query.filter_by(code=code).first()

    if not cert:
        return jsonify({'valid': False, 'error': 'Сертифікат не знайдено'})

    if cert.status == 'used':
        return jsonify({'valid': False, 'error': 'Сертифікат вже використано'})

    if cert.expires_at < date.today():
        return jsonify({'valid': False, 'error': 'Термін дії сертифіката закінчився'})

    return jsonify({
        'valid': True,
        'id': cert.id,
        'code': cert.code,
        'type': cert.type,
        'type_display': cert.type_display(),
        'value_display': cert.value_display(),
        'value_amount': str(cert.value_amount) if cert.value_amount else None,
        'value_size': cert.value_size,
        'expires_at': cert.expires_at.strftime('%d.%m.%Y'),
    })
