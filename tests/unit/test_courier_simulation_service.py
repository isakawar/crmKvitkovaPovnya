"""Unit tests for the in-house-courier simulation — optimizer injected as fakes."""
from datetime import date

import pytest

from app.services.route_optimizer_service import (
    RouteOptimizerAllFailedError,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
)
from app.services import courier_simulation_service as sim
from app.services.courier_simulation_service import (
    SimulationParams,
    _fmt,
    _minutes,
    compute_cost,
    simulate_day,
    simulate_month,
)

DEPOT = {"lat": 50.45, "lng": 30.52}


def _order(oid, tstart=None, tend=None):
    return {"id": oid, "city": "Київ", "address": "вул. Тестова", "house": str(oid),
            "lat": 50.45 + oid / 1000, "lng": 30.52 + oid / 1000,
            "delivery_window_start": tstart, "delivery_window_end": tend}


def _stop(oid, tstart=None, tend=None):
    o = _order(oid, tstart, tend)
    return {"id": oid, "lat": o["lat"], "lng": o["lng"], "address": o["address"],
            "timeStart": tstart, "timeEnd": tend}


def make_optimize_fn(routes, depot=DEPOT, failed=None, infeasible_once=False, all_failed=False):
    state = {"calls": 0}

    def optimize_fn(orders, *, start_time, num_couriers, time_buffer_min):
        state["calls"] += 1
        if all_failed:
            raise RouteOptimizerAllFailedError([{"id": o["id"]} for o in orders])
        if infeasible_once and state["calls"] == 1:
            raise RouteOptimizerInfeasibleError("треба більше", minimum_couriers_required=2)
        return {"routes": routes, "depot": depot, "failedOrders": failed or []}

    optimize_fn.state = state
    return optimize_fn


def make_recalc_fn(drive_min=20):
    """Accumulate ETAs: +drive, wait for window start, +15 service."""
    def recalc_fn(routes, *, start_time):
        t = _minutes(start_time)
        out = []
        for s in routes[0]["stops"]:
            t += drive_min
            ts = _minutes(s.get("timeStart"))
            if ts is not None and t < ts:
                t = ts
            out.append({**s, "eta": _fmt(t), "driveMin": drive_min, "serviceMin": 15})
            t += 15
        return {"routes": [{"stops": out, "totalDistanceKm": 4.2}]}
    return recalc_fn


# --------------------------------------------------------------------------- #
def test_minutes_fmt_roundtrip():
    assert _minutes("07:30") == 450
    assert _fmt(450) == "07:30"
    assert _minutes("∞") is None
    assert _minutes(None) is None
    assert _minutes("25:15") == 1515  # past midnight, tolerated


def test_compute_cost_hire_is_cheaper():
    p = SimulationParams()  # salary 25000, baseline 270, taxi 270
    c = compute_cost(covered=150, overflow=10, unroutable=0, params=p)
    assert c.current_total == 270 * 160
    assert c.inhouse_total == 25000 + 270 * 10
    assert c.delta == 270 * 160 - (25000 + 2700)
    assert c.delta > 0 and c.verdict == "НАЙМАТИ КУРʼЄРА"
    # baseline == taxi -> breakeven is "deliveries the courier must cover"
    assert c.breakeven_deliveries == pytest.approx(25000 / 270, abs=0.1)


def test_compute_cost_exclude_unroutable():
    p = SimulationParams(unroutable_as="exclude")
    c = compute_cost(covered=50, overflow=5, unroutable=8, params=p)
    assert c.current_total == 270 * 55            # unroutable dropped from both sides
    assert c.inhouse_total == 25000 + 270 * 5


def test_day_all_on_time():
    routes = [
        {"suggestedDepartureTime": "07:00", "stops": [_stop(1, tend="12:00"), _stop(2, tend="12:00")]},
        {"suggestedDepartureTime": "07:30", "stops": [_stop(3, tend="18:00")]},
    ]
    r = simulate_day("2026-08-01", [_order(1), _order(2), _order(3)],
                     SimulationParams(), make_optimize_fn(routes), make_recalc_fn())
    assert sorted(r.covered_ids) == [1, 2, 3]
    assert r.overflow_ids == []
    assert len(r.trips) == 2


def test_window_violation_drops_stop_and_tail():
    # Trip 2 runs after trip 1 + reload; stop 3 window closes at 08:00 -> missed.
    routes = [
        {"suggestedDepartureTime": "07:00", "stops": [_stop(1, tend="18:00")]},
        {"suggestedDepartureTime": "07:10", "stops": [_stop(3, tend="08:00"), _stop(4, tend="18:00")]},
    ]
    r = simulate_day("2026-08-01", [_order(1), _order(3), _order(4)],
                     SimulationParams(), make_optimize_fn(routes), make_recalc_fn())
    assert r.covered_ids == [1]
    assert sorted(r.overflow_ids) == [3, 4]


def test_shift_end_pushes_late_trips_to_taxi():
    routes = [
        {"suggestedDepartureTime": "07:00", "stops": [_stop(1, tend="23:00")]},
        {"suggestedDepartureTime": "07:05", "stops": [_stop(2, tend="23:00")]},
        {"suggestedDepartureTime": "07:10", "stops": [_stop(3, tend="23:00")]},
    ]
    p = SimulationParams(shift_start="07:00", shift_end="08:00", reload_buffer_min=30)
    r = simulate_day("2026-08-01", [_order(1), _order(2), _order(3)],
                     p, make_optimize_fn(routes), make_recalc_fn())
    assert 1 in r.covered_ids
    assert 3 in r.overflow_ids
    assert len(r.covered_ids) + len(r.overflow_ids) == 3


def test_infeasible_then_retry_succeeds():
    routes = [{"suggestedDepartureTime": "07:00", "stops": [_stop(1, tend="18:00")]}]
    opt = make_optimize_fn(routes, infeasible_once=True)
    r = simulate_day("2026-08-01", [_order(1)], SimulationParams(), opt, make_recalc_fn())
    assert opt.state["calls"] == 2
    assert r.covered_ids == [1]


def test_all_geocoding_failed_marks_unroutable():
    opt = make_optimize_fn([], all_failed=True)
    r = simulate_day("2026-08-01", [_order(1), _order(2)], SimulationParams(), opt, make_recalc_fn())
    assert sorted(r.unroutable_ids) == [1, 2]
    assert r.covered_ids == [] and r.overflow_ids == []


def test_optimizer_down_skips_day():
    def boom(*a, **k):
        raise RouteOptimizerError("немає зʼєднання")
    r = simulate_day("2026-08-01", [_order(1)], SimulationParams(), boom, make_recalc_fn())
    assert r.skipped is True
    assert r.total_candidates == 1
    assert r.notes


def test_reconcile_missing_stop_goes_to_overflow():
    # optimizer returns only 1 of 2 orders, none failed -> the other must be accounted.
    routes = [{"suggestedDepartureTime": "07:00", "stops": [_stop(1, tend="18:00")]}]
    r = simulate_day("2026-08-01", [_order(1), _order(2)],
                     SimulationParams(), make_optimize_fn(routes), make_recalc_fn())
    assert r.covered_ids == [1]
    assert r.overflow_ids == [2]
    assert len(r.covered_ids) + len(r.overflow_ids) + len(r.unroutable_ids) == 2


def test_simulate_month_aggregates_and_costs():
    routes = [{"suggestedDepartureTime": "07:00", "stops": [_stop(1, tend="18:00"), _stop(2, tend="18:00")]}]
    obd = {
        date(2026, 8, 1): [_order(1), _order(2)],
        date(2026, 8, 2): [_order(1), _order(2)],
    }
    res = simulate_month(obd, SimulationParams(), make_optimize_fn(routes), make_recalc_fn())
    assert res.total_deliveries == 4
    assert res.covered == 4
    assert res.total_trips == 2
    assert res.working_days == 2
    assert res.cost.current_total == 270 * 4
