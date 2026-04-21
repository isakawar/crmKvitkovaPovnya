"""
Tests for app/services/csv_import_service.py

Covers:
- normalize_phone: valid formats, invalid formats
- parse_client_field: @telegram, phone, plain text, (телеграм), (вотцап)
- parse_time_range: valid ranges, invalid
- parse_address: city extraction, street vs comment, nova_poshta, pickup
- normalize_delivery_type: mapping of Ukrainian/English types
- _strip_suffix: removing numeric duplicates
- find_existing_client: exact match, stripped match, phone-as-instagram
- build_preview_row_kvitkovapovnya: action determination, warnings
"""
import pytest
from app.services.csv_import_service import (
    normalize_phone,
    parse_client_field,
    parse_time_range,
    parse_address,
    normalize_delivery_type,
    _strip_suffix,
    find_existing_client,
    build_preview_row_kvitkovapovnya,
    preview_import_kvitkovapovnya,
)
from app.models import Client


# ── normalize_phone ──────────────────────────────────────────────────────────

def test_normalize_phone_full_format():
    assert normalize_phone('+380991234567') == '+380991234567'


def test_normalize_phone_without_plus():
    assert normalize_phone('380991234567') == '+380991234567'


def test_normalize_phone_short_format():
    assert normalize_phone('0991234567') == '+380991234567'


def test_normalize_phone_with_spaces():
    assert normalize_phone('+380 99 123 4567') == '+380991234567'


def test_normalize_phone_with_dashes():
    assert normalize_phone('+380-99-123-4567') == '+380991234567'


def test_normalize_phone_with_parens():
    result = normalize_phone('+380 (99) 123 4567')
    assert result is None


def test_normalize_phone_empty_returns_none():
    assert normalize_phone('') is None
    assert normalize_phone(None) is None


def test_normalize_phone_invalid_too_short():
    assert normalize_phone('+38099123456') is None


def test_normalize_phone_invalid_too_long():
    assert normalize_phone('+3809912345678') is None


def test_normalize_phone_multiline_takes_first():
    result = normalize_phone('+380991234567\n+380671112233')
    assert result == '+380991234567'


# ── parse_client_field ───────────────────────────────────────────────────────

def test_parse_client_at_prefix_is_telegram():
    result = parse_client_field('@my_telegram')
    assert result['telegram'] == '@my_telegram'
    assert result['instagram'] == '@my_telegram'


def test_parse_client_phone_only():
    result = parse_client_field('+380991234567')
    assert result['phone'] == '+380991234567'
    assert result['instagram'] == '+380991234567'


def test_parse_client_plain_text_is_instagram():
    result = parse_client_field('my_instagram')
    assert result['instagram'] == 'my_instagram'
    assert result['phone'] is None
    assert result['telegram'] is None


def test_parse_client_with_telegram_suffix():
    result = parse_client_field('Іван (телеграм)')
    assert result['telegram'] == 'Іван'
    assert result['instagram'] == 'Іван'


def test_parse_client_with_viber_suffix():
    result = parse_client_field('+380991234567(вотцап)')
    assert result['phone'] == '+380991234567'


def test_parse_client_empty():
    result = parse_client_field('')
    assert result['instagram'] is None
    assert result['phone'] is None
    assert result['telegram'] is None


# ── parse_time_range ─────────────────────────────────────────────────────────

def test_parse_time_range_valid():
    t_from, t_to = parse_time_range('8:00-11:00')
    assert t_from == '08:00'
    assert t_to == '11:00'


def test_parse_time_range_with_spaces():
    t_from, t_to = parse_time_range('9:00 - 12:00')
    assert t_from == '09:00'
    assert t_to == '12:00'


def test_parse_time_range_empty():
    t_from, t_to = parse_time_range('')
    assert t_from is None
    assert t_to is None


def test_parse_time_range_invalid():
    t_from, t_to = parse_time_range('not a time')
    assert t_from is None
    assert t_to is None


# ── parse_address ────────────────────────────────────────────────────────────

def test_parse_address_with_city_prefix():
    result = parse_address('м. Київ, Хрещатик 1')
    assert result['city'] == 'Київ'
    assert 'Хрещатик' in result['street']


def test_parse_address_with_known_city():
    result = parse_address('Бориспіль, вул. Шевченка 5')
    assert result['city'] == 'Бориспіль'


def test_parse_address_with_apartment_comment():
    result = parse_address('Київ, Хрещатик 1, кв. 10')
    assert result['address_comment'] != ''
    assert 'кв' in result['address_comment'].lower() or '10' in result['address_comment']


def test_parse_address_nova_poshta():
    result = parse_address('Нова Пошта, відділення 1')
    assert result['delivery_method'] == 'nova_poshta'
    assert result['is_pickup'] is False


def test_parse_address_pickup():
    result = parse_address('Самовивіз')
    assert result['is_pickup'] is True


def test_parse_address_empty():
    result = parse_address('')
    assert result['city'] == 'Київ'
    assert result['street'] == ''
    assert result['delivery_method'] == 'courier'


def test_parse_address_with_floor():
    result = parse_address('Київ, вул. Тестова 5, поверх 3')
    assert result['city'] == 'Київ'
    assert 'поверх' in result['address_comment'].lower() or '3' in result['address_comment']


# ── normalize_delivery_type ──────────────────────────────────────────────────

def test_normalize_delivery_type_weekly():
    assert normalize_delivery_type('weekly') == 'Weekly'
    assert normalize_delivery_type('Weekly') == 'Weekly'


def test_normalize_delivery_type_biweekly():
    assert normalize_delivery_type('bi-weekly') == 'Bi-weekly'
    assert normalize_delivery_type('Bi-weekly') == 'Bi-weekly'


def test_normalize_delivery_type_monthly():
    assert normalize_delivery_type('monthly') == 'Monthly'
    assert normalize_delivery_type('Monthly') == 'Monthly'
    assert normalize_delivery_type('Monthly') == 'Monthly'


def test_normalize_delivery_type_one_time():
    assert normalize_delivery_type('one-time') == 'One-time'
    assert normalize_delivery_type('') == 'One-time'


# ── _strip_suffix ────────────────────────────────────────────────────────────

def test_strip_suffix_removes_paren_number():
    assert _strip_suffix('chrisfetisova (1)') == 'chrisfetisova'


def test_strip_suffix_removes_trailing_number():
    assert _strip_suffix('lanatremtii 2') == 'lanatremtii'


def test_strip_suffix_no_change():
    assert _strip_suffix('clean_name') == 'clean_name'


def test_strip_suffix_empty():
    assert _strip_suffix('') == ''


# ── find_existing_client ─────────────────────────────────────────────────────

def test_find_existing_client_by_instagram(session):
    c = Client(instagram='find_me')
    session.add(c)
    session.commit()

    result = find_existing_client(instagram='find_me')
    assert result is not None
    assert result.instagram == 'find_me'


def test_find_existing_client_by_stripped_instagram(session):
    c = Client(instagram='base_user')
    session.add(c)
    session.commit()

    result = find_existing_client(instagram='base_user (1)')
    assert result is not None
    assert result.instagram == 'base_user'


def test_find_existing_client_by_phone(session):
    c = Client(instagram='phone_user', phone='+380991112233')
    session.add(c)
    session.commit()

    result = find_existing_client(phone='+380991112233')
    assert result is not None


def test_find_existing_client_not_found(session):
    result = find_existing_client(instagram='nonexistent')
    assert result is None


# ── build_preview_row_kvitkovapovnya ─────────────────────────────────────────

def _raw_row(**overrides):
    base = {
        'row_num': 2,
        'raw_client': 'test_user',
        'recipient_name': 'R',
        'recipient_phone': '+380991234567',
        'recipient_phones_extra': [],
        'delivery_type_raw': 'щотижнева',
        'delivery_day_raw': 'понеділок',
        'size': 'M',
        'city': 'Київ',
        'address_raw': 'Хрещатик 1',
        'address_comment_raw': '',
        'for_whom': 'Я',
        'marketing_source': '',
        'planned_date_raw': '01.04.2026',
        'delivery_number_raw': '1',
        'is_wedding_raw': '',
        'discount_raw': '',
    }
    base.update(overrides)
    return base


def test_preview_row_action_subscription():
    raw = _raw_row(delivery_number_raw='1')
    row = build_preview_row_kvitkovapovnya(raw)
    assert row['action'] == 'subscription'


def test_preview_row_action_one_time():
    raw = _raw_row(delivery_number_raw='0')
    row = build_preview_row_kvitkovapovnya(raw)
    assert row['action'] == 'one_time'


def test_preview_row_action_client_only():
    raw = _raw_row(delivery_number_raw='')
    row = build_preview_row_kvitkovapovnya(raw)
    assert row['action'] == 'client_only'


def test_preview_row_action_subscription_followup():
    raw = _raw_row(delivery_number_raw='5')
    row = build_preview_row_kvitkovapovnya(raw)
    assert row['action'] == 'subscription_followup'


def test_preview_row_warning_missing_date():
    raw = _raw_row(planned_date_raw='', delivery_number_raw='1')
    row = build_preview_row_kvitkovapovnya(raw)
    assert any('дата' in w.lower() for w in row['warnings'])


def test_preview_row_wedding_detection():
    raw = _raw_row(is_wedding_raw='так')
    row = build_preview_row_kvitkovapovnya(raw)
    assert row['is_wedding'] is True


def test_preview_row_discount_parsing():
    raw = _raw_row(discount_raw='10%')
    row = build_preview_row_kvitkovapovnya(raw)
    assert row['discount'] == 10
