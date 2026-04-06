"""
Tests for app/models/certificate.py

Covers Certificate.effective_status() and Certificate.is_active() logic.
These are pure model-method tests; they only need an app context for
the SQLAlchemy column types to resolve correctly.
"""
import datetime
import pytest
from app.models.certificate import Certificate


def _cert(status='active', days_until_expiry=30):
    """Build an unsaved Certificate for method testing."""
    expires = datetime.date.today() + datetime.timedelta(days=days_until_expiry)
    return Certificate(
        code='Р0001',
        type='amount',
        value_amount=500,
        expires_at=expires,
        status=status,
    )


# ── effective_status ──────────────────────────────────────────────────────────

def test_effective_status_active_when_not_expired(app):
    cert = _cert(status='active', days_until_expiry=30)
    assert cert.effective_status() == 'active'


def test_effective_status_expired_when_past_expiry(app):
    cert = _cert(status='active', days_until_expiry=-1)
    assert cert.effective_status() == 'expired'


def test_effective_status_used_regardless_of_expiry(app):
    """A 'used' certificate is always 'used', even if the date has passed."""
    cert = _cert(status='used', days_until_expiry=-10)
    assert cert.effective_status() == 'used'


def test_effective_status_expires_today_is_active(app):
    """A certificate expiring today is still active (expires_at == today)."""
    cert = _cert(status='active', days_until_expiry=0)
    # expires_at = today, so expires_at < today is False → should be 'active'
    assert cert.effective_status() == 'active'


# ── is_active ─────────────────────────────────────────────────────────────────

def test_is_active_true_when_active_and_not_expired(app):
    cert = _cert(status='active', days_until_expiry=10)
    assert cert.is_active() is True


def test_is_active_false_when_expired(app):
    cert = _cert(status='active', days_until_expiry=-1)
    assert cert.is_active() is False


def test_is_active_false_when_used(app):
    cert = _cert(status='used', days_until_expiry=30)
    assert cert.is_active() is False


def test_is_active_consistent_with_effective_status(app):
    """is_active() should match (effective_status() == 'active')."""
    for days, status in [(30, 'active'), (-1, 'active'), (30, 'used'), (-1, 'used')]:
        cert = _cert(status=status, days_until_expiry=days)
        assert cert.is_active() == (cert.effective_status() == 'active')
