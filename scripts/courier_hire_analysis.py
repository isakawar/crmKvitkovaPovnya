"""Offline analysis: "what if we hired ONE salaried in-house courier?"

Simulates, day by day, how many of a month's real courier deliveries a single
salaried courier could physically have covered — doing several <=3h trips per
day, respecting every delivery's time window — how many would still have gone to
taxi, and whether that is cheaper than paying third-party couriers per delivery.

Read-only. Calls the existing route optimizer (FastAPI service). Nothing is
written to the DB.

Usage (inside Docker):
    docker compose exec web python scripts/courier_hire_analysis.py --month 2026-08
    docker compose exec web python scripts/courier_hire_analysis.py --month 2026-08 \
        --salary 25000 --shift-start 07:00 --shift-end 19:00 --sensitivity

Limitations (see also the HTML report footer):
  * The optimizer's depot is hard-coded ("вулиця Нагірна, 18, Київ"); drive times
    are relative to it. Re-point the optimizer's DEPOT_ADDRESS if the real shop
    address differs.
  * Optimizer routes are "open" (no return-to-depot leg) so the trip count is
    mildly optimistic; --phase-a-buffer-min and --reload-buffer-min compensate.
  * The 270 UAH per-delivery cost is an assumption — the schema stores no
    per-delivery cost anywhere.
"""
import argparse
import calendar
import json
import os
import sys
from collections import defaultdict
from datetime import date
from html import escape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.delivery import Delivery
from app.services.route_optimizer_service import (
    _delivery_to_order_json,
    optimize_orders_json,
    recalculate,
)
from app.services.courier_simulation_service import (
    SimulationParams,
    compute_cost,
    simulate_month,
)

DEFAULT_STATUSES = "Доставлено,Розподілено,Очікує"


# --------------------------------------------------------------------------- #
# args
# --------------------------------------------------------------------------- #
def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--month", help="YYYY-MM")
    p.add_argument("--day", help="YYYY-MM-DD — simulate a single day (for tuning)")
    p.add_argument("--from", dest="date_from", help="YYYY-MM-DD range start (with --to)")
    p.add_argument("--to", dest="date_to", help="YYYY-MM-DD range end (inclusive)")
    p.add_argument("--shift-start", default="07:00")
    p.add_argument("--shift-end", default="19:00")
    p.add_argument("--max-trip-min", type=int, default=180)
    p.add_argument("--reload-buffer-min", type=int, default=30)
    p.add_argument("--time-buffer-min", type=int, default=15)
    p.add_argument("--phase-a-buffer-min", type=int, default=0)
    p.add_argument("--couriers", type=int, default=1)
    p.add_argument("--salary", type=float, default=25000.0)
    p.add_argument("--car-cost", type=float, default=0.0)
    p.add_argument("--baseline-cost", type=float, default=270.0)
    p.add_argument("--taxi-cost", type=float, default=270.0)
    p.add_argument("--statuses", default=DEFAULT_STATUSES)
    p.add_argument("--include-cancelled", action="store_true")
    p.add_argument("--unroutable", choices=["taxi", "exclude"], default="taxi")
    p.add_argument("--mode", choices=["decompose", "iterative"], default="decompose")
    p.add_argument("--sensitivity", action="store_true",
                   help="also print a shift-length x courier-count grid")
    p.add_argument("--optimizer-url", default=None)
    p.add_argument("--optimizer-timeout", type=int, default=120)
    p.add_argument("--html", default=None, help="HTML report path (default: courier_hire_analysis_<month>.html)")
    p.add_argument("--csv", default=None, help="per-day CSV dump path")
    p.add_argument("--json", dest="json_path", default=None, help="raw JSON dump path")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def params_from_args(args) -> SimulationParams:
    return SimulationParams(
        shift_start=args.shift_start,
        shift_end=args.shift_end,
        max_trip_min=args.max_trip_min,
        reload_buffer_min=args.reload_buffer_min,
        time_buffer_min=args.time_buffer_min,
        phase_a_buffer_min=args.phase_a_buffer_min,
        num_couriers=args.couriers,
        salary_uah=args.salary,
        car_cost_uah=args.car_cost,
        baseline_cost_uah=args.baseline_cost,
        taxi_cost_uah=args.taxi_cost,
        unroutable_as=args.unroutable,
        mode=args.mode,
    )


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_orders_by_day(first: date, last: date, statuses: list[str], include_cancelled: bool):
    q = Delivery.query.filter(
        Delivery.delivery_date >= first,
        Delivery.delivery_date <= last,
        Delivery.delivery_method == "courier",
        Delivery.is_pickup.isnot(True),
    )
    if not include_cancelled:
        q = q.filter(Delivery.status.in_(statuses))

    orders_by_day: dict[date, list[dict]] = defaultdict(list)
    for d in q.order_by(Delivery.delivery_date).all():
        orders_by_day[d.delivery_date].append(_delivery_to_order_json(d))
    return dict(orders_by_day)


def make_optimizer_callables(optimizer_url: str, timeout: int):
    def optimize_fn(orders, *, start_time, num_couriers, time_buffer_min):
        return optimize_orders_json(
            orders, optimizer_url,
            start_time=start_time, num_couriers=num_couriers,
            time_buffer_min=time_buffer_min, timeout=timeout,
        )

    def recalculate_fn(routes, *, start_time):
        return recalculate(routes, optimizer_url, start_time=start_time, timeout=timeout)

    return optimize_fn, recalculate_fn


# --------------------------------------------------------------------------- #
# console output
# --------------------------------------------------------------------------- #
def print_report(result, params, months=1.0):
    m = f"{result.year}-{result.month:02d}"
    span_label = "місяць" if months >= 0.98 else f"~{months * 30.44:.0f} дн."
    print()
    print("=" * 64)
    print(f"АНАЛІЗ: ШТАТНИЙ КУРʼЄР vs СТОРОННІ   ({m})")
    print("=" * 64)
    print(f"  Зміна:                {params.shift_start}–{params.shift_end}  "
          f"({params.shift_len_min // 60} год)")
    print(f"  Макс. ходка в дорозі: {params.max_trip_min} хв")
    print(f"  Буфер перезавантаж.:  {params.reload_buffer_min} хв")
    print(f"  Курʼєрів:             {params.num_couriers}")
    print(f"  Зарплата/міс:         {params.salary_uah:,.0f} грн   авто/міс: {params.car_cost_uah:,.0f} грн")
    print(f"  Ціна доставки зараз:  {params.baseline_cost_uah:,.0f} грн   такси: {params.taxi_cost_uah:,.0f} грн")
    print(f"  Період симуляції:     {span_label}  (зп в порівнянні × {months:.2f})")
    print("-" * 64)
    print(f"  Доставок за період:       {result.total_deliveries}")
    print(f"  Покрив би штатний курʼєр:  {result.covered}")
    print(f"  Довелося б таксі:          {result.overflow}")
    print(f"  Не вдалося геокодувати:    {result.unroutable}")
    print(f"  Ходок усього:              {result.total_trips}")
    print(f"  Робочих днів:              {result.working_days}   "
          f"ходок/день: {result.total_trips / result.working_days:.1f}"
          if result.working_days else f"  Робочих днів:              0")
    print(f"  Завантаження курʼєра:      {result.courier_utilization_pct:.1f}%")
    if result.skipped_days:
        print(f"  ⚠ Пропущено днів (оптимізатор недоступний): {result.skipped_days}")
    print("-" * 64)
    c = result.cost
    if result.working_days <= 2:
        print("  ⚠ Мало днів — цифри вартості орієнтовні, дивись покрито/таксі/ходки.")
    fixed = (params.num_couriers * params.salary_uah + params.car_cost_uah) * months
    print(f"  Зараз (сторонні):         {c.current_total:,.0f} грн")
    print(f"  Свій курʼєр (зп {fixed:,.0f} + таксі overflow): {c.inhouse_total:,.0f} грн")
    print(f"  Різниця:                  {c.delta:,.0f} грн   ({c.delta_per_delivery:+,.1f} грн/доставку)")
    print(f"  Точка беззбитковості:     {c.breakeven_deliveries:.0f} доставок")
    print(f"  ВЕРДИКТ:                  {c.verdict}")
    print("=" * 64)

    print("\n  За днями:")
    print(f"  {'дата':<12} {'дост':>5} {'покрито':>8} {'таксі':>6} {'ходок':>6} {'зайнято':>8}")
    for d in result.days:
        if not d.total_candidates:
            continue
        busy = f"{d.busy_min // 60}г{d.busy_min % 60:02d}" if d.trips else "—"
        flag = "  SKIP" if d.skipped else ""
        print(f"  {str(d.day):<12} {d.total_candidates:>5} {len(d.covered_ids):>8} "
              f"{len(d.overflow_ids):>6} {len(d.trips):>6} {busy:>8}{flag}")
        for note in d.notes:
            print(f"      · {note}")


def print_sensitivity(orders_by_day, base_params, optimize_fn, recalculate_fn, months=1.0):
    print("\n  Чутливість (покрито / таксі / вердикт):")
    shift_variants = [("07:00", "15:00"), ("07:00", "17:00"), ("07:00", "19:00")]
    print(f"  {'зміна':<14} {'1 курʼєр':>22} {'2 курʼєри':>22}")
    for ss, se in shift_variants:
        row = f"  {ss}-{se:<8}"
        for couriers in (1, 2):
            p = SimulationParams(**{**base_params.__dict__, "shift_start": ss,
                                    "shift_end": se, "num_couriers": couriers})
            r = simulate_month(orders_by_day, p, optimize_fn, recalculate_fn, months=months)
            row += f"  {r.covered:>6}/{r.overflow:<5}{r.cost.verdict[:9]:>10}"
        print(row)


# --------------------------------------------------------------------------- #
# HTML report
# --------------------------------------------------------------------------- #
def build_html(result, params, months=1.0) -> str:
    m = f"{result.year}-{result.month:02d}"
    c = result.cost
    span = "місяць" if months >= 0.98 else f"~{months * 30.44:.0f} днів"
    fixed = (params.num_couriers * params.salary_uah + params.car_cost_uah) * months
    day_rows = [d for d in result.days if d.total_candidates]
    max_cand = max((d.total_candidates for d in day_rows), default=1)

    bars = []
    for d in day_rows:
        cov = len(d.covered_ids)
        tax = len(d.overflow_ids) + len(d.unroutable_ids)
        w_cov = 100 * cov / max_cand
        w_tax = 100 * tax / max_cand
        bars.append(
            f'<div class="row"><span class="dl">{escape(str(d.day))}</span>'
            f'<span class="bar"><i class="cov" style="width:{w_cov:.1f}%"></i>'
            f'<i class="tax" style="width:{w_tax:.1f}%"></i></span>'
            f'<span class="num">{cov}<small>/{tax}</small></span></div>'
        )

    def kpi(label, value, sub=""):
        return (f'<div class="kpi"><div class="v">{escape(str(value))}</div>'
                f'<div class="l">{escape(label)}</div>'
                f'<div class="s">{escape(sub)}</div></div>')

    verdict_cls = "good" if c.delta > 0 else "bad"

    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Штатний курʼєр — аналіз {m}</title>
<style>
  body {{ font: 15px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
         background: #f6f7f9; color: #1c1e21; }}
  .wrap {{ max-width: 900px; margin: 0 auto; padding: 32px 20px 64px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .muted {{ color: #65676b; font-size: 13px; margin-bottom: 24px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
           gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: #fff; border: 1px solid #e4e6eb; border-radius: 10px; padding: 16px; }}
  .kpi .v {{ font-size: 24px; font-weight: 700; }}
  .kpi .l {{ font-size: 13px; color: #65676b; margin-top: 2px; }}
  .kpi .s {{ font-size: 12px; color: #8a8d91; margin-top: 4px; }}
  .verdict {{ padding: 16px 20px; border-radius: 10px; font-size: 18px; font-weight: 700;
              margin-bottom: 24px; }}
  .verdict.good {{ background: #e3f4e9; color: #1a7f37; }}
  .verdict.bad {{ background: #fdecea; color: #c0392b; }}
  .card {{ background: #fff; border: 1px solid #e4e6eb; border-radius: 10px;
           padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; margin: 0 0 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #f0f1f3; }}
  td.r {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .row {{ display: flex; align-items: center; gap: 10px; margin: 3px 0; font-size: 12px; }}
  .row .dl {{ width: 84px; color: #65676b; flex: none; }}
  .row .bar {{ flex: 1; display: flex; height: 14px; background: #f0f1f3; border-radius: 3px;
               overflow: hidden; }}
  .row .bar i {{ display: block; height: 100%; }}
  .row .bar .cov {{ background: #2d7ff9; }}
  .row .bar .tax {{ background: #f0a020; }}
  .row .num {{ width: 60px; text-align: right; font-variant-numeric: tabular-nums; flex: none; }}
  .row .num small {{ color: #f0a020; }}
  .legend {{ font-size: 12px; color: #65676b; margin-bottom: 10px; }}
  .legend b.cov {{ color: #2d7ff9; }} .legend b.tax {{ color: #f0a020; }}
  .foot {{ font-size: 12px; color: #8a8d91; margin-top: 24px; }}
  .foot li {{ margin: 3px 0; }}
</style></head><body><div class="wrap">
<h1>Штатний курʼєр vs сторонні — {m}</h1>
<div class="muted">Зміна {params.shift_start}–{params.shift_end} ·
  макс. ходка {params.max_trip_min} хв · курʼєрів {params.num_couriers} ·
  зарплата {params.salary_uah:,.0f} грн/міс</div>

<div class="verdict {verdict_cls}">{escape(c.verdict)} &nbsp; ({c.delta:+,.0f} грн за {span})</div>

<div class="kpis">
  {kpi(f"Доставок за {span}", result.total_deliveries)}
  {kpi("Покрив би штатний", result.covered,
       f"{100 * result.covered / result.total_deliveries:.0f}%" if result.total_deliveries else "")}
  {kpi("Довелося б таксі", result.overflow + result.unroutable)}
  {kpi("Завантаження курʼєра", f"{result.courier_utilization_pct:.0f}%",
       f"{result.total_trips} ходок за {result.working_days} дн.")}
</div>

<div class="card"><h2>Вартість за {span}</h2>
<table>
  <tr><td>Зараз (сторонні курʼєри)</td><td class="r">{c.current_total:,.0f} грн</td></tr>
  <tr><td>Свій курʼєр: зарплата + авто</td>
      <td class="r">{fixed:,.0f} грн</td></tr>
  <tr><td>Свій курʼєр: доставки на таксі (overflow)</td>
      <td class="r">{c.inhouse_total - fixed:,.0f} грн</td></tr>
  <tr><td><b>Свій курʼєр разом</b></td><td class="r"><b>{c.inhouse_total:,.0f} грн</b></td></tr>
  <tr><td><b>Різниця</b></td><td class="r"><b>{c.delta:+,.0f} грн</b></td></tr>
  <tr><td>Точка беззбитковості</td><td class="r">{c.breakeven_deliveries:.0f} доставок</td></tr>
</table></div>

<div class="card"><h2>Покриття за днями</h2>
<div class="legend"><b class="cov">■</b> покрив би штатний &nbsp;
  <b class="tax">■</b> таксі</div>
{"".join(bars)}
</div>

<div class="foot">Припущення та обмеження:
<ul>
  <li>Депо оптимізатора зашите ("вулиця Нагірна, 18, Київ") — час у дорозі відносно нього.</li>
  <li>Маршрути "відкриті" (без плеча повернення) → кількість ходок трохи занижена.</li>
  <li>{params.baseline_cost_uah:,.0f} грн за доставку — припущення (у системі немає вартості доставки).</li>
  <li>Старі адреси без координат геокодує сам оптимізатор; що не вдалося — окрема категорія.</li>
</ul></div>
</div></body></html>"""


def dump_csv(result, path):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "candidates", "covered", "overflow", "unroutable", "trips", "busy_min", "skipped", "notes"])
        for d in result.days:
            if not d.total_candidates:
                continue
            w.writerow([d.day, d.total_candidates, len(d.covered_ids), len(d.overflow_ids),
                        len(d.unroutable_ids), len(d.trips), d.busy_min, int(d.skipped),
                        " | ".join(d.notes)])


def dump_json(result, path):
    payload = {
        "month": f"{result.year}-{result.month:02d}",
        "totals": {
            "deliveries": result.total_deliveries, "covered": result.covered,
            "overflow": result.overflow, "unroutable": result.unroutable,
            "trips": result.total_trips, "working_days": result.working_days,
            "skipped_days": result.skipped_days,
            "utilization_pct": result.courier_utilization_pct,
        },
        "cost": {
            "current_total": result.cost.current_total,
            "inhouse_total": result.cost.inhouse_total,
            "delta": result.cost.delta,
            "delta_per_delivery": result.cost.delta_per_delivery,
            "breakeven_deliveries": result.cost.breakeven_deliveries,
            "verdict": result.cost.verdict,
        },
        "days": [
            {"date": str(d.day), "candidates": d.total_candidates,
             "covered": len(d.covered_ids), "overflow": len(d.overflow_ids),
             "unroutable": len(d.unroutable_ids), "trips": len(d.trips),
             "busy_min": d.busy_min, "skipped": d.skipped, "notes": d.notes}
            for d in result.days if d.total_candidates
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    args = parse_args(argv)
    if not args.month and not args.day and not (args.date_from and args.date_to):
        raise SystemExit("потрібен --month YYYY-MM, --day YYYY-MM-DD або --from/--to")
    if args.day:
        first = last = date(*(int(x) for x in args.day.split("-")))
        tag = args.day
    elif args.date_from and args.date_to:
        first = date(*(int(x) for x in args.date_from.split("-")))
        last = date(*(int(x) for x in args.date_to.split("-")))
        tag = f"{args.date_from}_{args.date_to}"
    else:
        y, mo = (int(x) for x in args.month.split("-"))
        first = date(y, mo, 1)
        last = date(y, mo, calendar.monthrange(y, mo)[1])
        tag = args.month
    params = params_from_args(args)
    statuses = [s.strip() for s in args.statuses.split(",") if s.strip()]
    # Prorate the salary to the simulated span (a full --month == 1.0).
    months = 1.0 if args.month else ((last - first).days + 1) / 30.44

    app = create_app()
    with app.app_context():
        from flask import current_app
        optimizer_url = args.optimizer_url or current_app.config.get("ROUTE_OPTIMIZER_URL") or "http://localhost:8000"
        if args.verbose:
            print(f"optimizer: {optimizer_url}")

        orders_by_day = load_orders_by_day(first, last, statuses, args.include_cancelled)
        total = sum(len(v) for v in orders_by_day.values())
        if not total:
            print(f"За {tag} немає курʼєрських доставок за фільтром.")
            return
        if args.verbose:
            print(f"{total} доставок у {len(orders_by_day)} днях")

        optimize_fn, recalculate_fn = make_optimizer_callables(optimizer_url, args.optimizer_timeout)
        result = simulate_month(orders_by_day, params, optimize_fn, recalculate_fn, months=months)

    print_report(result, params, months=months)
    if args.sensitivity:
        with app.app_context():
            print_sensitivity(orders_by_day, params, optimize_fn, recalculate_fn, months)

    html_path = args.html or f"courier_hire_analysis_{tag}.html"
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html(result, params, months=months))
    print(f"\nHTML-звіт: {html_path}")

    if args.csv:
        dump_csv(result, args.csv)
        print(f"CSV: {args.csv}")
    if args.json_path:
        dump_json(result, args.json_path)
        print(f"JSON: {args.json_path}")


if __name__ == "__main__":
    main()
