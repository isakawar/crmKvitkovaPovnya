"""
Tests for app/services/courier_service.py

Covers:
- create_courier: happy path
- get_all_couriers: returns all, ordered by id desc
"""
import pytest
from app.models import Courier
from app.services.courier_service import create_courier, get_all_couriers


# ── create_courier ───────────────────────────────────────────────────────────

def test_create_courier_stores_name_and_phone(session):
    courier = create_courier('Олексій', '+380991234567')
    assert courier.name == 'Олексій'
    assert courier.phone == '+380991234567'
    assert courier.deliveries_count == 0


def test_create_courier_persists_to_db(session):
    courier = create_courier('Марія', '+380671112233')
    fetched = Courier.query.get(courier.id)
    assert fetched is not None
    assert fetched.name == 'Марія'


# ── get_all_couriers ─────────────────────────────────────────────────────────

def test_get_all_couriers_returns_empty(session):
    assert get_all_couriers() == []


def test_get_all_couriers_returns_all_ordered_by_id_desc(session):
    c1 = create_courier('A', '+380990000001')
    c2 = create_courier('B', '+380990000002')
    c3 = create_courier('C', '+380990000003')

    result = get_all_couriers()
    assert len(result) == 3
    assert result[0].id > result[1].id > result[2].id
    assert result[0].name == 'C'
    assert result[1].name == 'B'
    assert result[2].name == 'A'
