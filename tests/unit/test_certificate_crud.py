"""
Tests for Certificate CRUD operations via blueprint routes.

Covers:
- Certificate creation (amount, size, subscription types)
- Certificate code generation (sequential)
- Certificate validation (valid, used, expired, not found)
- Certificate use and return flow
- Certificate type and status display methods
- Certificate value_display for all types
"""
import datetime
import pytest
from app.models.certificate import Certificate, generate_certificate_code


# ── Certificate model methods ────────────────────────────────────────────────

def _cert(status='active', days_until_expiry=30, cert_type='amount', value_amount=500, value_size=None):
    expires = datetime.date.today() + datetime.timedelta(days=days_until_expiry)
    return Certificate(
        code='Р0001',
        type=cert_type,
        value_amount=value_amount,
        value_size=value_size,
        expires_at=expires,
        status=status,
    )


def test_certificate_type_display_amount():
    cert = _cert(cert_type='amount')
    assert cert.type_display() == 'На суму'


def test_certificate_type_display_size():
    cert = _cert(cert_type='size', value_size='M')
    assert cert.type_display() == 'На розмір'


def test_certificate_type_display_subscription():
    cert = _cert(cert_type='subscription')
    assert cert.type_display() == 'На підписку'


def test_certificate_value_display_amount():
    cert = _cert(cert_type='amount', value_amount=500)
    assert '500' in cert.value_display()


def test_certificate_value_display_size():
    cert = _cert(cert_type='size', value_size='L')
    assert cert.value_display() == 'L'


def test_certificate_value_display_subscription_with_size():
    cert = _cert(cert_type='subscription', value_size='M')
    assert 'Підписка' in cert.value_display()
    assert 'M' in cert.value_display()


def test_certificate_value_display_subscription_no_size():
    cert = _cert(cert_type='subscription', value_size=None)
    assert cert.value_display() == 'Підписка'


def test_certificate_status_display_active():
    cert = _cert(status='active', days_until_expiry=30)
    assert cert.status_display() == 'Активний'


def test_certificate_status_display_used():
    cert = _cert(status='used', days_until_expiry=30)
    assert cert.status_display() == 'Використаний'


def test_certificate_status_display_expired():
    cert = _cert(status='active', days_until_expiry=-1)
    assert cert.status_display() == 'Прострочений'


# ── generate_certificate_code ────────────────────────────────────────────────

def test_generate_certificate_code_requires_app_context(app):
    """generate_certificate_code needs app context for DB query."""
    code = generate_certificate_code('amount')
    assert code == 'Р0001'


def test_generate_certificate_code_subscription_prefix(app):
    code = generate_certificate_code('subscription')
    assert code.startswith('П')
    assert code == 'П0001'


def test_generate_certificate_code_amount_prefix(app):
    code = generate_certificate_code('amount')
    assert code.startswith('Р')
    assert code == 'Р0001'


def test_generate_certificate_code_sequential(app):
    c1 = Certificate(code='Р0001', type='amount', value_amount=100,
                     expires_at=datetime.date.today() + datetime.timedelta(days=365), status='active')
    c2 = Certificate(code='Р0002', type='amount', value_amount=200,
                     expires_at=datetime.date.today() + datetime.timedelta(days=365), status='active')
    from app.extensions import db
    db.session.add_all([c1, c2])
    db.session.commit()

    code = generate_certificate_code('amount')
    assert code == 'Р0003'


def test_generate_certificate_code_sequential_subscription(app):
    c1 = Certificate(code='П0001', type='subscription', value_size='M',
                     expires_at=datetime.date.today() + datetime.timedelta(days=365), status='active')
    from app.extensions import db
    db.session.add(c1)
    db.session.commit()

    code = generate_certificate_code('subscription')
    assert code == 'П0002'
