"""
Tests for app/services/subscription_service.py

These tests are PURE (no DB access): they only call the date-calculation
helpers that are plain Python functions.

Covers:
- calculate_next_delivery_date (Weekly / Bi-weekly / Monthly)
- build_delivery_dates (always 4 dates, weekday anchor)
- build_delivery_dates_n (arbitrary count)
- calculate_reschedule_plan (Monthly skipped, gap threshold)
"""
import datetime
import pytest
from app.services.subscription_service import (
    calculate_next_delivery_date,
    build_delivery_dates,
    build_delivery_dates_n,
    WEEKLY_MIN_GAP_DAYS,
    BIWEEKLY_MIN_GAP_DAYS,
    _get_first_valid_date,
)

# Monday = 0, …, Sunday = 6
MON = 0
TUE = 1
WED = 2
THU = 3
FRI = 4
SAT = 5
SUN = 6

# A known Monday to use as anchor
_MONDAY = datetime.date(2026, 3, 30)   # confirmed Monday
assert _MONDAY.weekday() == MON


# ── calculate_next_delivery_date: Weekly ─────────────────────────────────────

def test_weekly_same_weekday_is_plus7():
    """Weekly: same desired weekday → exactly +7 days."""
    result = calculate_next_delivery_date(_MONDAY, 'Weekly', MON)
    assert result == _MONDAY + datetime.timedelta(days=7)
    assert result.weekday() == MON


def test_weekly_different_weekday_snaps_forward():
    """Weekly starting on Monday, desired Friday: should land on the next Friday."""
    result = calculate_next_delivery_date(_MONDAY, 'Weekly', FRI)
    assert result.weekday() == FRI
    # base + 7 days = next Monday, then we snap to Friday of that week
    assert (result - _MONDAY).days == 7 + 4  # Mon+7=Mon, then +4=Fri


def test_weekly_sequence_has_consistent_7day_gap():
    dates = build_delivery_dates(_MONDAY, 'Weekly', 'ПН')
    for i in range(1, len(dates)):
        assert (dates[i] - dates[i - 1]).days == 7


# ── calculate_next_delivery_date: Bi-weekly ──────────────────────────────────

def test_biweekly_base_is_plus14():
    result = calculate_next_delivery_date(_MONDAY, 'Bi-weekly', MON)
    assert result == _MONDAY + datetime.timedelta(days=14)
    assert result.weekday() == MON


def test_biweekly_snap_does_not_exceed_20_days():
    """
    Suspicious area #1 (BUSINESS_FUNCTIONS.md): Bi-weekly snap can add up to 20 days.
    We document the actual maximum to guard against regressions.
    """
    # Try all 7 weekday combinations from a Monday start
    for desired in range(7):
        result = calculate_next_delivery_date(_MONDAY, 'Bi-weekly', desired)
        gap = (result - _MONDAY).days
        assert gap <= 20, f'Bi-weekly gap is {gap} days for desired weekday {desired}'
        assert result.weekday() == desired


def test_biweekly_sequence_weekday_consistent():
    dates = build_delivery_dates(_MONDAY, 'Bi-weekly', 'ПН')
    assert all(d.weekday() == MON for d in dates)


# ── calculate_next_delivery_date: Monthly ────────────────────────────────────

def test_monthly_base_is_near_plus28():
    result = calculate_next_delivery_date(_MONDAY, 'Monthly', MON)
    gap = (result - _MONDAY).days
    # nearest Monday to +28 days; gap must be between 25 and 31
    assert 25 <= gap <= 31
    assert result.weekday() == MON


def test_monthly_snap_within_3_days_of_28():
    """Monthly should snap to nearest weekday, never more than 3 days off +28."""
    for desired in range(7):
        result = calculate_next_delivery_date(_MONDAY, 'Monthly', desired)
        base_28 = _MONDAY + datetime.timedelta(days=28)
        drift = abs((result - base_28).days)
        assert drift <= 3, f'Monthly drift {drift} for weekday {desired}'
        assert result.weekday() == desired


# ── build_delivery_dates ──────────────────────────────────────────────────────

def test_build_delivery_dates_returns_4():
    dates = build_delivery_dates(_MONDAY, 'Weekly', 'ПН')
    assert len(dates) == 4


def test_build_delivery_dates_first_is_input():
    dates = build_delivery_dates(_MONDAY, 'Weekly', 'ПН')
    assert dates[0] == _MONDAY


def test_build_delivery_dates_all_same_weekday():
    dates = build_delivery_dates(_MONDAY, 'Weekly', 'ПН')
    assert all(d.weekday() == MON for d in dates)


# ── build_delivery_dates_n ────────────────────────────────────────────────────

def test_build_delivery_dates_n_arbitrary_count():
    dates = build_delivery_dates_n(_MONDAY, 'Weekly', 'ПН', 6)
    assert len(dates) == 6
    assert all(d.weekday() == MON for d in dates)


def test_build_delivery_dates_n_zero_returns_empty():
    assert build_delivery_dates_n(_MONDAY, 'Weekly', 'ПН', 0) == []


# ── _get_first_valid_date (reschedule threshold) ──────────────────────────────

def test_get_first_valid_weekly_respects_min_gap():
    """
    If the first candidate falls within WEEKLY_MIN_GAP_DAYS from new_date,
    the result must be pushed a full week forward.
    """
    # new_date is Thursday; desired weekday is Friday (1 day away → ≤ 4 threshold)
    thursday = datetime.date(2026, 4, 2)  # Thursday
    assert thursday.weekday() == THU

    result = _get_first_valid_date(thursday, 'Weekly', 'ПТ')
    gap = (result - thursday).days
    assert gap > WEEKLY_MIN_GAP_DAYS, (
        f'Expected gap > {WEEKLY_MIN_GAP_DAYS}, got {gap}'
    )
    assert result.weekday() == FRI


def test_get_first_valid_biweekly_respects_min_gap():
    """
    If first candidate is within BIWEEKLY_MIN_GAP_DAYS from new_date,
    result must be shifted by 14 days extra.
    """
    # new_date Monday, desired Thursday (3 days away → ≤ 9 threshold)
    result = _get_first_valid_date(_MONDAY, 'Bi-weekly', 'ЧТ')
    gap = (result - _MONDAY).days
    assert gap > BIWEEKLY_MIN_GAP_DAYS, (
        f'Expected gap > {BIWEEKLY_MIN_GAP_DAYS}, got {gap}'
    )
    assert result.weekday() == THU
