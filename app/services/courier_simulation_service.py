"""Offline simulation: could ONE salaried in-house courier have covered a month
of historical deliveries, and would it be cheaper than per-delivery third parties?

Pure logic — no Flask, no SQLAlchemy, no HTTP. The optimizer is injected as two
callables so the whole thing is unit-testable with fakes:

    optimize_fn(orders, *, start_time, num_couriers, time_buffer_min) -> optimizer result dict
    recalculate_fn(routes, *, start_time) -> optimizer result dict

``orders`` are the serialized order dicts produced by
``route_optimizer_service._delivery_to_order_json``:
``{id, city, address, house, lat?, lng?, delivery_window_start?, delivery_window_end?}``.

Two phases per day (mode="decompose", the default):

  A. One optimize_fn call on the whole day → K routes, each already <= 3h and
     already time-window feasible (the optimizer enforces MAX_ROUTE_DURATION_MIN
     and auto-picks the minimum courier count). Each route = one candidate trip.
  B. Simulate ONE courier doing those K trips back-to-back: walk a clock from the
     shift start, recalculate_fn each trip from the real (shifted) departure time,
     and move any stop whose ETA blows its window — plus the rest of that trip —
     to the taxi overflow. When the clock passes the shift end, remaining trips
     overflow too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.route_optimizer_service import (
    RouteOptimizerAllFailedError,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
)

_DEPOT_RETURN_ID = -1
_DEPOT_RETURN_ADDR = "__DEPOT_RETURN__"
_MAX_ROUNDS = 8  # decompose/sequence rounds per day before the rest goes to taxi


# --------------------------------------------------------------------------- #
# time helpers
# --------------------------------------------------------------------------- #
def _minutes(hhmm) -> int | None:
    """"HH:MM" -> minutes since midnight. None for empty / '∞' / unparseable.

    Tolerates values past 24:00 (the optimizer emits e.g. "25:30")."""
    if hhmm is None or hhmm == "" or hhmm == "∞":
        return None
    try:
        parts = str(hhmm).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def _fmt(minutes) -> str:
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# --------------------------------------------------------------------------- #
# data classes
# --------------------------------------------------------------------------- #
@dataclass
class SimulationParams:
    shift_start: str = "07:00"
    shift_end: str = "19:00"
    max_trip_min: int = 180            # flowers-in-the-car ceiling per trip
    reload_buffer_min: int = 30        # depot turnaround between trips
    time_buffer_min: int = 15          # optimizer's own window-end safety margin
    phase_a_buffer_min: int = 0        # extra Phase-A headroom for the missing return leg
    num_couriers: int = 1
    salary_uah: float = 25000.0        # per courier, per month
    car_cost_uah: float = 0.0          # car + fuel, per month, total
    baseline_cost_uah: float = 270.0   # what a delivery costs today (third party)
    taxi_cost_uah: float = 270.0       # what an overflow delivery would cost by taxi
    unroutable_as: str = "taxi"        # "taxi" | "exclude"
    mode: str = "decompose"            # "decompose" | "iterative"

    @property
    def shift_len_min(self) -> int:
        return _minutes(self.shift_end) - _minutes(self.shift_start)


@dataclass
class StopResult:
    delivery_id: int | None
    eta: str | None
    window_end: str | None
    on_time: bool


@dataclass
class Trip:
    depart: str
    end: str
    transit_min: int          # depart -> last kept delivery (flowers in the car)
    drive_km: float
    stops: list[StopResult] = field(default_factory=list)


@dataclass
class DaySimulationResult:
    day: date
    total_candidates: int
    covered_ids: list = field(default_factory=list)
    overflow_ids: list = field(default_factory=list)
    unroutable_ids: list = field(default_factory=list)
    trips: list[Trip] = field(default_factory=list)
    skipped: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def busy_min(self) -> int:
        return sum(_minutes(t.end) - _minutes(t.depart) for t in self.trips)


@dataclass
class CostComparison:
    current_total: float
    inhouse_total: float
    delta: float                    # > 0 -> hiring is cheaper
    delta_per_delivery: float
    breakeven_deliveries: float

    @property
    def verdict(self) -> str:
        return "НАЙМАТИ КУРʼЄРА" if self.delta > 0 else "ЗАЛИШИТИ СТОРОННІХ"


@dataclass
class MonthlySimulationResult:
    year: int
    month: int
    params: SimulationParams
    days: list[DaySimulationResult]
    total_deliveries: int
    covered: int
    overflow: int
    unroutable: int
    total_trips: int
    working_days: int
    skipped_days: int
    courier_utilization_pct: float
    cost: CostComparison


# --------------------------------------------------------------------------- #
# Phase A — decompose a day into <=3h candidate trips
# --------------------------------------------------------------------------- #
def _decompose_day(orders: list[dict], params: SimulationParams, optimize_fn, start_time=None):
    """-> (candidate_routes, depot_dict, unroutable_ids, infeasible_ids)."""
    buf = params.time_buffer_min + params.phase_a_buffer_min
    start_time = start_time or params.shift_start

    def _run(num_couriers):
        return optimize_fn(
            orders,
            start_time=start_time,
            num_couriers=num_couriers,
            time_buffer_min=buf,
        )

    try:
        result = _run(None)
    except RouteOptimizerAllFailedError:
        return [], {}, [o["id"] for o in orders], []
    except RouteOptimizerInfeasibleError as exc:
        retry_n = exc.minimum_couriers_required or len(orders)
        try:
            result = _run(retry_n)
        except RouteOptimizerInfeasibleError:
            # Physically unservable within the windows even with many couriers.
            return [], {}, [], [o["id"] for o in orders]
        except RouteOptimizerAllFailedError:
            return [], {}, [o["id"] for o in orders], []

    routes = result.get("routes", []) or []
    depot = result.get("depot") or {}
    failed = result.get("failedOrders") or []
    unroutable_ids = [f.get("id") for f in failed if f.get("id") is not None]
    return routes, depot, unroutable_ids, []


# --------------------------------------------------------------------------- #
# Phase B — one courier, sequential trips
# --------------------------------------------------------------------------- #
def _route_stop_ids(route: dict) -> list:
    return [s.get("id") for s in route.get("stops", [])]


def _build_recalc_route(route: dict, depot: dict, courier_id: int) -> dict:
    """Fixed stop order + one synthetic depot stop so recalc returns the return leg."""
    stops = []
    for s in route.get("stops", []):
        stops.append({
            "id": s.get("id"),
            "lat": s.get("lat"),
            "lng": s.get("lng"),
            "address": s.get("address") or "",
            "timeStart": s.get("timeStart"),
            "timeEnd": s.get("timeEnd"),
        })
    d_lat, d_lng = depot.get("lat"), depot.get("lng")
    if d_lat is not None and d_lng is not None:
        stops.append({
            "id": _DEPOT_RETURN_ID,
            "lat": d_lat,
            "lng": d_lng,
            "address": _DEPOT_RETURN_ADDR,
        })
    return {"courierId": courier_id, "stops": stops}


def _route_departure(route: dict, fallback: int) -> int:
    """When the courier should leave the depot for this trip.

    The optimizer already picks ``suggestedDepartureTime`` so the route stays
    within the 3h cap with minimal waiting — the courier waits in the depot
    (flowers in the fridge), not on the road. Fall back to "early enough to
    reach the first window" when it's missing."""
    dep = _minutes(route.get("suggestedDepartureTime"))
    if dep is not None:
        return dep
    starts = [_minutes(s.get("timeStart")) for s in route.get("stops", [])]
    starts = [s for s in starts if s is not None]
    if starts:
        return max(fallback, min(starts) - 30)
    return fallback


def _sort_routes(routes: list[dict], shift_start_min: int) -> list[dict]:
    return sorted(routes, key=lambda r: _route_departure(r, shift_start_min))


def _sequence_trips(candidate_routes, depot, params: SimulationParams, recalculate_fn, start_clock=None):
    """-> (trips, covered_ids, overflow_ids, end_clock)."""
    shift_start = _minutes(params.shift_start)
    shift_end = _minutes(params.shift_end)
    clock = shift_start if start_clock is None else start_clock
    trips: list[Trip] = []
    covered_ids: list = []
    overflow_ids: list = []

    for idx, route in enumerate(_sort_routes(candidate_routes, shift_start), start=1):
        raw_stops = route.get("stops", []) or []
        if not raw_stops:
            continue

        # Leave the depot under the first window — but never before the courier
        # is back from the previous trip.
        depart = max(clock, _route_departure(route, clock))
        if depart >= shift_end:
            overflow_ids.extend(_route_stop_ids(route))
            continue

        # Stops missing coords can't be recalculated — straight to overflow.
        usable = [s for s in raw_stops if s.get("lat") is not None and s.get("lng") is not None]
        overflow_ids.extend(s.get("id") for s in raw_stops if s not in usable)
        if not usable:
            continue

        recalc_route = _build_recalc_route({"stops": usable}, depot, idx)
        out = recalculate_fn([recalc_route], start_time=_fmt(depart))
        out_routes = out.get("routes") or [{}]
        out_stops = out_routes[0].get("stops", []) or []

        has_return = bool(out_stops) and out_stops[-1].get("id") == _DEPOT_RETURN_ID
        return_leg = out_stops[-1].get("driveMin", 0) if has_return else 0
        real_stops = out_stops[:-1] if has_return else out_stops

        # Keep the on-time prefix; the first window violation drops itself + the tail.
        kept: list[dict] = []
        for s in real_stops:
            eta = _minutes(s.get("eta"))
            wend = _minutes(s.get("timeEnd"))
            if wend is not None and eta is not None and eta > wend:
                break
            kept.append(s)
        overflow_ids.extend(s.get("id") for s in real_stops[len(kept):])

        # Trailing-drop until the trip fits both the 3h freshness cap (measured
        # from the real departure, not the shift start) and the shift end.
        def _span(last):
            return _minutes(last["eta"]) + last.get("serviceMin", 15) - depart

        def _trip_end(last):
            return _minutes(last["eta"]) + last.get("serviceMin", 15) + (return_leg or 0)

        while kept and (_span(kept[-1]) > params.max_trip_min or _trip_end(kept[-1]) > shift_end):
            overflow_ids.append(kept.pop().get("id"))

        if not kept:
            # Nothing served — don't advance the clock; a later trip may still
            # have an open early window.
            continue

        last = kept[-1]
        trip_end = _trip_end(last)
        covered_ids.extend(s.get("id") for s in kept)
        stop_results = [
            StopResult(
                delivery_id=s.get("id"),
                eta=s.get("eta"),
                window_end=s.get("timeEnd"),
                on_time=True,
            )
            for s in kept
        ]
        trips.append(Trip(
            depart=_fmt(depart),
            end=_fmt(trip_end),
            transit_min=int(round(_span(last))),
            drive_km=round(float(out_routes[0].get("totalDistanceKm") or 0), 2),
            stops=stop_results,
        ))
        clock = trip_end + params.reload_buffer_min

    return trips, covered_ids, overflow_ids, clock


# --------------------------------------------------------------------------- #
# iterative mode — rolling optimize_fn, "second opinion"
# --------------------------------------------------------------------------- #
def _iterative_day(orders: list[dict], params: SimulationParams, optimize_fn):
    """-> (trips, covered_ids, overflow_ids). Approximate: no explicit return leg."""
    remaining = list(orders)
    clock = _minutes(params.shift_start)
    shift_end = _minutes(params.shift_end)
    trips: list[Trip] = []
    covered_ids: list = []
    overflow_ids: list = []

    while remaining and clock < shift_end:
        try:
            result = optimize_fn(
                remaining,
                start_time=_fmt(clock),
                num_couriers=1,
                time_buffer_min=params.time_buffer_min,
            )
        except RouteOptimizerInfeasibleError:
            break
        except RouteOptimizerAllFailedError:
            break

        routes = result.get("routes") or []
        stops = routes[0].get("stops", []) if routes else []
        failed = result.get("failedOrders") or []
        failed_ids = {f.get("id") for f in failed if f.get("id") is not None}
        served_ids = {s.get("id") for s in stops if s.get("id") is not None}

        if not served_ids and not failed_ids:
            break  # no progress — bail out, remaining -> overflow below

        overflow_ids.extend(failed_ids)

        if stops:
            kept = list(stops)
            while kept and _minutes(kept[-1]["eta"]) + kept[-1].get("serviceMin", 15) > shift_end:
                overflow_ids.append(kept.pop().get("id"))
            served_ids = {s.get("id") for s in kept}
            if kept:
                last = kept[-1]
                trip_end = _minutes(last["eta"]) + last.get("serviceMin", 15)
                covered_ids.extend(s.get("id") for s in kept)
                trips.append(Trip(
                    depart=_fmt(clock),
                    end=_fmt(trip_end),
                    transit_min=int(round(trip_end - clock)),
                    drive_km=round(float(routes[0].get("totalDistanceKm") or 0), 2),
                    stops=[
                        StopResult(s.get("id"), s.get("eta"), s.get("timeEnd"), True)
                        for s in kept
                    ],
                ))
                clock = trip_end + params.reload_buffer_min

        remaining = [o for o in remaining if o["id"] not in served_ids and o["id"] not in failed_ids]

    overflow_ids.extend(o["id"] for o in remaining)
    return trips, covered_ids, overflow_ids


# --------------------------------------------------------------------------- #
# per-day driver
# --------------------------------------------------------------------------- #
def simulate_day(day, orders, params, optimize_fn, recalculate_fn) -> DaySimulationResult:
    all_ids = [o["id"] for o in orders]
    if not orders:
        return DaySimulationResult(day=day, total_candidates=0)

    notes: list[str] = []
    trips: list[Trip] = []
    covered_ids: list = []
    unroutable_ids: list = []
    infeasible_ids: list = []

    if params.mode == "iterative":
        try:
            _, _, unroutable_ids, infeasible_ids = _decompose_day(orders, params, optimize_fn)
        except RouteOptimizerError as exc:
            return DaySimulationResult(
                day=day, total_candidates=len(all_ids), skipped=True,
                notes=[f"оптимізатор недоступний: {exc}"],
            )
        routable = [o for o in orders if o["id"] not in unroutable_ids]
        trips, covered_ids, overflow_ids = _iterative_day(routable, params, optimize_fn)
    else:
        # Decompose -> sequence -> re-decompose whatever overflowed, now from
        # where the clock stands, until a round adds nothing (or the shift ends).
        pending = list(orders)
        clock = _minutes(params.shift_start)
        shift_end = _minutes(params.shift_end)
        overflow_ids = []
        for rnd in range(_MAX_ROUNDS):
            if not pending or clock >= shift_end:
                break
            try:
                routes, depot, unroutable_r, infeasible_r = _decompose_day(
                    pending, params, optimize_fn, start_time=_fmt(clock))
            except RouteOptimizerError as exc:
                if rnd == 0:
                    return DaySimulationResult(
                        day=day, total_candidates=len(all_ids), skipped=True,
                        notes=[f"оптимізатор недоступний: {exc}"],
                    )
                notes.append(f"раунд {rnd + 1}: оптимізатор недоступний, решту — на таксі")
                break
            unroutable_ids += unroutable_r
            infeasible_ids += infeasible_r
            done = set(unroutable_r) | set(infeasible_r)
            pending = [o for o in pending if o["id"] not in done]
            if not routes or not pending:
                break
            t, cov, _over, clock = _sequence_trips(
                routes, depot, params, recalculate_fn, start_clock=clock)
            trips += t
            covered_ids += cov
            cov_set = set(cov)
            new_pending = [o for o in pending if o["id"] not in cov_set]
            if len(new_pending) == len(pending):
                break  # no progress this round
            pending = new_pending
        overflow_ids = [o["id"] for o in pending]

    overflow_ids = list(overflow_ids) + list(infeasible_ids)

    if infeasible_ids:
        notes.append(f"{len(infeasible_ids)} доставок не вкладаються у вікна навіть кількома курʼєрами")

    if None in covered_ids or None in overflow_ids:
        notes.append("частина зупинок без id — звірка приблизна")

    # Reconcile against the candidate set — covered wins, then unroutable, and
    # everything else (overflow, infeasible, silently dropped) is taxi.
    id_set = [i for i in all_ids if i is not None]
    covered_set = {i for i in covered_ids if i is not None and i in set(id_set)}
    unroutable_set = {i for i in unroutable_ids if i is not None} - covered_set
    overflow_set = set(id_set) - covered_set - unroutable_set

    return DaySimulationResult(
        day=day,
        total_candidates=len(all_ids),
        covered_ids=[i for i in id_set if i in covered_set],
        overflow_ids=[i for i in id_set if i in overflow_set],
        unroutable_ids=[i for i in id_set if i in unroutable_set],
        trips=trips,
        notes=notes,
    )


# --------------------------------------------------------------------------- #
# cost model
# --------------------------------------------------------------------------- #
def compute_cost(covered, overflow, unroutable, params: SimulationParams, months: float = 1.0) -> CostComparison:
    """`months` prorates the fixed cost (salary + car) to the simulated span so a
    week / single-day run compares like-for-like."""
    n = covered + overflow
    unroutable_taxi = unroutable if params.unroutable_as == "taxi" else 0

    current = params.baseline_cost_uah * (n + unroutable_taxi)
    fixed = (params.num_couriers * params.salary_uah + params.car_cost_uah) * months
    inhouse = fixed + params.taxi_cost_uah * (overflow + unroutable_taxi)
    delta = current - inhouse

    denom = params.baseline_cost_uah - params.taxi_cost_uah
    if denom > 0.01:
        breakeven = fixed / denom
    elif params.baseline_cost_uah > 0.01:
        breakeven = fixed / params.baseline_cost_uah
    else:
        breakeven = 0.0

    return CostComparison(
        current_total=round(current, 2),
        inhouse_total=round(inhouse, 2),
        delta=round(delta, 2),
        delta_per_delivery=round(delta / n, 2) if n else 0.0,
        breakeven_deliveries=round(breakeven, 1),
    )


# --------------------------------------------------------------------------- #
# month aggregation
# --------------------------------------------------------------------------- #
def simulate_month(orders_by_day, params, optimize_fn, recalculate_fn, months: float = 1.0) -> MonthlySimulationResult:
    days = [
        simulate_day(day, orders_by_day[day], params, optimize_fn, recalculate_fn)
        for day in sorted(orders_by_day)
    ]

    covered = sum(len(d.covered_ids) for d in days)
    overflow = sum(len(d.overflow_ids) for d in days)
    unroutable = sum(len(d.unroutable_ids) for d in days)
    total_deliveries = sum(d.total_candidates for d in days)
    total_trips = sum(len(d.trips) for d in days)
    working_days = sum(1 for d in days if d.total_candidates and not d.skipped)
    skipped_days = sum(1 for d in days if d.skipped)

    available_min = working_days * params.shift_len_min
    busy_min = sum(d.busy_min for d in days)
    utilization = round(100 * busy_min / available_min, 1) if available_min else 0.0

    cost = compute_cost(covered, overflow, unroutable, params, months=months)

    sample = next((d.day for d in days), None)
    year = sample.year if sample else 0
    month = sample.month if sample else 0

    return MonthlySimulationResult(
        year=year, month=month, params=params, days=days,
        total_deliveries=total_deliveries, covered=covered, overflow=overflow,
        unroutable=unroutable, total_trips=total_trips, working_days=working_days,
        skipped_days=skipped_days, courier_utilization_pct=utilization, cost=cost,
    )
