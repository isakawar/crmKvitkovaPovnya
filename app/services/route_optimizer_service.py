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


def optimize_deliveries(deliveries: Iterable, optimizer_url: str):
    orders = [_delivery_to_order_json(d) for d in deliveries]
    payload = {"orders": orders}

    url = f"{optimizer_url.rstrip('/')}/api/optimize/json"
    headers = {"Content-Type": "application/json"}

    api_key = os.environ.get("OPTIMIZER_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
    except requests.RequestException as exc:
        raise RouteOptimizerError(f"Немає з'єднання з route optimizer ({url}): {exc}") from exc

    body = {}
    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code == 200:
        return body

    if response.status_code == 422 and body.get("error") == "INFEASIBLE":
        raise RouteOptimizerInfeasibleError(
            body.get("message") or "Неможливо побудувати маршрут з поточними параметрами",
            body.get("minimum_couriers_required"),
            body.get("reason"),
        )

    detail = body.get("detail")
    if isinstance(detail, str):
        raise RouteOptimizerError(detail)
    raise RouteOptimizerError(f"Оптимізатор повернув помилку HTTP {response.status_code}")


def routes_result_to_csv(result: dict) -> str:
    output = io.StringIO()
    fieldnames = [
        "courier_id",
        "stop_no",
        "address",
        "eta",
        "drive_min",
        "wait_min",
        "time_start",
        "time_end",
        "lat",
        "lng",
        "route_total_drive_min",
        "route_total_distance_km",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    routes = result.get("routes", [])
    for route in routes:
        courier_id = route.get("courierId")
        total_drive = route.get("totalDriveMin")
        total_distance = route.get("totalDistanceKm")
        stops = route.get("stops", [])
        for idx, stop in enumerate(stops, start=1):
            writer.writerow(
                {
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
                }
            )
    return output.getvalue()
