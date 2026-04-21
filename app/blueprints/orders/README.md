# orders blueprint

Handles all order, delivery, and route-generation HTTP endpoints.

## Module map

| File | Endpoints | Responsibility |
|------|-----------|----------------|
| `orders.py` | `/orders`, `/orders/new`, `/orders/<id>/edit`, `/orders/<id>/delete`, `/orders/<id>/dependencies`, `/orders/<id>/bouquet_type`, `/orders/<id>/extend-subscription`, `/clients/search`, `/orders/last-order`, `/orders/export/csv`, `/orders/extend-form-from-delivery/<id>` | Order CRUD, client search, CSV export |
| `deliveries.py` | `/orders/deliveries/<id>/dependencies`, `/orders/deliveries/<id>/delete`, `/orders/deliveries/time`, `/orders/deliveries/reschedule-subsequent` | Delivery mutation and reschedule |
| `route_generator.py` | `/route-generator` (GET/POST), `/route-generator/recalculate`, `/route-generator/optimize-csv`, `/route-generator/job/<id>`, `/route-generator/deliveries`, `/route-generator/export-csv` | Route optimisation UI and API |
| `route_saver.py` | `/route-generator/save` | Persist optimised routes to DB |
| `route_distribute.py` | `/route-generator/distribute` (GET/POST), `/route-generator/distribute/apply` | Distribute unrouted deliveries to existing routes |
| `_helpers.py` | — | `parse_ymd`, `parse_hm`, `parse_eta` date/time utilities |

## Naming conventions

- `date_str` — raw string from a URL query param (e.g. `?date=2024-01-15`)
- `selected_date_str` — raw string from a JSON request body key `selected_date`
- `selected_date` — `datetime.date` object after parsing

## Business logic boundary

Route/delivery persistence logic lives here. Optimisation calls delegate to
`app/services/route_optimizer_service.py`. Order/delivery creation delegates to
`app/services/order_service.py` and `app/services/subscription_service.py`.
