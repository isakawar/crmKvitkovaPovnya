import csv
import io
import os
from typing import Iterable

import requests


class RouteOptimizerError(Exception):
    """Base exception for route optimizer integration errors."""


class RouteOptimizerInfeasibleError(RouteOptimizerError):
    """Raised when optimizer reports infeasible routes for given constraints."""

    def __init__(self, message: str, minimum_couriers_required: int | None = None, reason: str | None = None):
        super().__init__(message)
        self.minimum_couriers_required = minimum_couriers_required
        self.reason = reason


def _delivery_to_order_json(delivery) -> dict:
    order = delivery.order
    city = (order.city if order else "") or ""
    street = (delivery.street or (order.street if order else "")) or ""
    house = (delivery.building_number or (order.building_number if order else "")) or ""
    item = {
        "id": delivery.id,
        "city": city,
        "address": street,
        "house": house,
    }
    if delivery.time_from:
        item["delivery_window_start"] = delivery.time_from
    if delivery.time_to:
        item["delivery_window_end"] = delivery.time_to
    return item


def _ensure_stats(result: dict) -> dict:
    if "stats" not in result:
        routes = result.get("routes", [])
        result["stats"] = {
            "totalDeliveries": sum(len(r.get("stops", [])) for r in routes),
            "numCouriers": len(routes),
            "totalDistanceKm": round(sum(r.get("totalDistanceKm") or 0 for r in routes), 2),
            "totalDriveMin": round(sum(r.get("totalDriveMin") or 0 for r in routes)),
        }
    return result


def _parse_error(body: dict, status_code: int):
    """Raise appropriate exception for non-200 responses."""
    if status_code == 422 and body.get("error") == "INFEASIBLE":
        raise RouteOptimizerInfeasibleError(
            body.get("message") or "Неможливо побудувати маршрут з поточними параметрами",
            body.get("minimum_couriers_required"),
            body.get("reason"),
        )
    detail = body.get("detail") or body.get("message") or body.get("error")
    if isinstance(detail, str):
        raise RouteOptimizerError(detail)
    raise RouteOptimizerError(f"Оптимізатор повернув помилку HTTP {status_code}")


def optimize_json(deliveries: Iterable, optimizer_url: str) -> dict:
    """/api/optimize/json — always synchronous, returns result directly."""
    orders = [_delivery_to_order_json(d) for d in deliveries]
    url = f"{optimizer_url.rstrip('/')}/api/optimize/json"
    headers = {"Content-Type": "application/json"}

    api_key = os.environ.get("OPTIMIZER_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        response = requests.post(url, json={"orders": orders}, headers=headers, timeout=120)
    except requests.RequestException as exc:
        raise RouteOptimizerError(f"Немає з'єднання з route optimizer: {exc}") from exc

    body = {}
    try:
        body = response.json()
    except ValueError:
        pass

    if response.status_code == 200:
        return _ensure_stats(body)

    _parse_error(body, response.status_code)


def submit_csv_job(file_stream, filename: str, optimizer_url: str) -> tuple:
    """/api/optimize (CSV) — async (Redis) or sync (no Redis).
    Returns (job_id, result):
      - async: (job_id_str, None)
      - sync:  (None, result_dict)
    """
    url = f"{optimizer_url.rstrip('/')}/api/optimize"
    headers = {}

    api_key = os.environ.get("OPTIMIZER_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        response = requests.post(
            url,
            files={"file": (filename, file_stream, "text/csv")},
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RouteOptimizerError(f"Немає з'єднання з route optimizer: {exc}") from exc

    body = {}
    try:
        body = response.json()
    except ValueError:
        pass

    if response.status_code != 200:
        _parse_error(body, response.status_code)

    job_id = body.get("jobId")
    status = body.get("status")

    # Sync mode: jobId="sync", status="done", result={...}
    if status in ("done", "completed") and job_id:
        result = body.get("result") or body
        return None, _ensure_stats(result)

    # Async mode: jobId="<uuid>", status="pending"
    if job_id:
        return job_id, None

    # Fallback: result returned directly (no jobId wrapper)
    if body.get("routes") is not None:
        return None, _ensure_stats(body)

    raise RouteOptimizerError("Unexpected optimizer response format")


def get_job_status(job_id: str, optimizer_url: str) -> dict:
    """Proxy GET /api/jobs/{job_id}, augment completed result with stats."""
    api_key = os.environ.get("OPTIMIZER_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else {}
    url = f"{optimizer_url.rstrip('/')}/api/jobs/{job_id}"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        body = resp.json()
    except Exception as exc:
        raise RouteOptimizerError(str(exc)) from exc

    if resp.status_code != 200:
        raise RouteOptimizerError(f"HTTP {resp.status_code}")

    if body.get("status") in ("completed", "done"):
        result = body.get("result") or body
        body["result"] = _ensure_stats(result)

    return body




def routes_result_to_csv(result: dict) -> str:
    output = io.StringIO()
    fieldnames = [
        "courier_id", "stop_no", "address", "eta", "drive_min", "wait_min",
        "time_start", "time_end", "lat", "lng",
        "route_total_drive_min", "route_total_distance_km",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for route in result.get("routes", []):
        courier_id = route.get("courierId")
        total_drive = route.get("totalDriveMin")
        total_distance = route.get("totalDistanceKm")
        for idx, stop in enumerate(route.get("stops", []), start=1):
            writer.writerow({
                "courier_id": courier_id,
                "stop_no": idx,
                "address": stop.get("address", ""),
                "eta": stop.get("eta", ""),
                "drive_min": stop.get("driveMin", ""),
                "wait_min": stop.get("waitMin", ""),
                "time_start": stop.get("timeStart", ""),
                "time_end": stop.get("timeEnd", ""),
                "lat": stop.get("lat", ""),
                "lng": stop.get("lng", ""),
                "route_total_drive_min": total_drive,
                "route_total_distance_km": total_distance,
            })
    return output.getvalue()
