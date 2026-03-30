"""
Tests for app/services/client_service.py

Covers: create_client (happy path, duplicates, phone validation),
        search_clients (by instagram, by phone).
"""
import pytest
from app.models import Client
from app.services.client_service import create_client, search_clients


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_client(session, instagram, phone=None, telegram=None):
    c = Client(instagram=instagram, phone=phone, telegram=telegram)
    session.add(c)
    session.commit()
    return c


# ── create_client: happy path ─────────────────────────────────────────────────

def test_create_client_ok(session):
    client, err = create_client('@flower_shop', phone='+380991111111')
    assert err is None
    assert client is not None
    # @ prefix should be stripped when stored
    assert client.instagram == 'flower_shop'
    assert client.phone == '+380991111111'


def test_create_client_normalizes_at_prefix(session):
    client, err = create_client('@my_client')
    assert err is None
    assert client.instagram == 'my_client'


def test_create_client_no_instagram_returns_error(session):
    client, err = create_client('')
    assert client is None
    assert err


# ── create_client: phone validation ──────────────────────────────────────────

@pytest.mark.parametrize('bad_phone', [
    '0991111111',        # missing +380 prefix
    '+38099111111',      # too short
    '+3809911111111',    # too long
    '+380991111111a',    # contains letter
    '380991111111',      # no leading +
])
def test_create_client_invalid_phone(session, bad_phone):
    client, err = create_client(f'user_{bad_phone}', phone=bad_phone)
    assert client is None
    assert err is not None


def test_create_client_valid_phone_accepted(session):
    client, err = create_client('valid_phone_user', phone='+380671234567')
    assert err is None
    assert client is not None


# ── create_client: duplicate detection ───────────────────────────────────────

def test_create_client_duplicate_instagram_returns_structured_error(session):
    _make_client(session, instagram='dup_insta')

    client, err = create_client('dup_insta')
    assert client is None
    assert isinstance(err, dict)
    assert err['type'] == 'duplicate'
    assert err['field'] == 'instagram'
    assert 'client_id' in err


def test_create_client_duplicate_instagram_with_at_prefix(session):
    """Both '@handle' and 'handle' should be treated as the same Instagram."""
    _make_client(session, instagram='at_user')

    client, err = create_client('@at_user')
    assert client is None
    assert isinstance(err, dict)
    assert err['field'] == 'instagram'


def test_create_client_duplicate_telegram_returns_structured_error(session):
    _make_client(session, instagram='tg_owner', telegram='my_telegram')

    client, err = create_client('another_insta', telegram='my_telegram')
    assert client is None
    assert isinstance(err, dict)
    assert err['type'] == 'duplicate'
    assert err['field'] == 'telegram'


def test_create_client_duplicate_phone_returns_structured_error(session):
    _make_client(session, instagram='phone_owner', phone='+380501234567')

    client, err = create_client('another_insta2', phone='+380501234567')
    assert client is None
    assert isinstance(err, dict)
    assert err['type'] == 'duplicate'
    assert err['field'] == 'phone'


# ── search_clients ────────────────────────────────────────────────────────────

def test_search_clients_by_instagram(session):
    _make_client(session, instagram='searchable_user')
    _make_client(session, instagram='other_user')

    result = search_clients(q='searchable')
    found_instagrams = [c.instagram for c in result.items]
    assert 'searchable_user' in found_instagrams
    assert 'other_user' not in found_instagrams


def test_search_clients_by_phone(session):
    _make_client(session, instagram='phone_search_user', phone='+380991112233')

    result = search_clients(q='1112233')
    found_instagrams = [c.instagram for c in result.items]
    assert 'phone_search_user' in found_instagrams
