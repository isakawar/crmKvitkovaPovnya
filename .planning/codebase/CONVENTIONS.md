# Coding Conventions

**Analysis Date:** 2026-04-02

## Naming Patterns

**Files:**
- Blueprint routes: `routes.py` in `app/blueprints/{feature}/` directories
- Service modules: `{entity}_service.py` in `app/services/` (e.g., `order_service.py`, `client_service.py`)
- Model files: `{entity}.py` in `app/models/` or core models use simple lowercase (`order.py`, `client.py`)
- Migrations: `{description}.py` in `migrations/versions/`

**Functions:**
- snake_case throughout (e.g., `get_or_create_client`, `create_order_and_deliveries`, `group_deliveries_by_date`)
- Helper functions in tests prefixed with underscore: `_make_client()`, `_base_form()`
- Service functions are action-oriented: `create_*`, `update_*`, `get_*`, `search_*`, `delete_*`
- Pagination functions: `paginate_orders()` returns tuple of (paginated_list, has_next_page)

**Variables:**
- Local variables: snake_case (`delivery_date`, `custom_amount`, `is_pickup`)
- Constants: SCREAMING_SNAKE_CASE (e.g., `SUBSCRIPTION_TYPES = ['Weekly', 'Monthly', 'Bi-weekly']`)
- Model attributes: lowercase with underscores matching DB column names

**Types & Classes:**
- Model classes: PascalCase (e.g., `Order`, `Client`, `Delivery`, `Courier`)
- Blueprint names: lowercase (e.g., `orders_bp`, `clients_bp`, `auth_bp`)
- Exception types: PascalCase with `Error` suffix (e.g., `RouteOptimizerError`)

## Code Style

**Formatting:**
- No automated formatter configured (`.flake8`, `.pylintrc`, etc. not present)
- Consistent with Python PEP 8 conventions observed in codebase
- Imports grouped: stdlib, third-party, local (see Import Organization below)

**Linting:**
- No linting tool enforced in codebase
- Code organization and style maintained manually by convention

## Import Organization

**Order:**
1. Standard library imports (e.g., `os`, `datetime`, `logging`, `re`)
2. Third-party imports (e.g., Flask, SQLAlchemy, pytest)
3. Local imports from `app` package (models, services, extensions)

**Example pattern from `app/services/order_service.py`:**
```python
from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.recipient_phone import RecipientPhone
import datetime
import logging
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)
```

**Path Aliases:**
- Explicit relative paths used (no `@` aliases configured)
- Absolute imports from `app` package (`from app.extensions import db`, `from app.models import Order`)

**Late imports for circular dependency avoidance:**
- Local imports inside functions when needed (e.g., in `app/services/order_service.py:97`: `from app.models.subscription import Subscription as _Subscription`)

## Error Handling

**Patterns:**
- Services return `(result, error)` tuple where error is `None` on success
  - Example: `get_or_create_client()` returns `(client, error_message)` or `(None, error_string)`
- Structured errors: return dict with keys `type`, `field`, `client_id`, `error` for duplicate detection
  - Example: `{'type': 'duplicate', 'field': 'instagram', 'client_id': 123, 'error': 'message'}`
- Flask routes catch exceptions and log them, then return error flashes to user
- Date parsing: try/except pattern for strptime with `ValueError` caught silently (see `get_orders` lines 126-130)
- Validation in services (phone format, required fields) returns structured error dict

**Error messages:**
- User-facing messages in Ukrainian (e.g., `'Клієнт з таким Instagram не знайдений!'`)
- Error strings returned as-is from service layer to route handlers

## Logging

**Framework:** Python's built-in `logging` module

**Patterns:**
- Logger instantiated per module: `logger = logging.getLogger(__name__)`
- Typical usage: `logger.info()`, `logger.error()`
- Logged operations: CRUD events, state transitions, user actions
- Example from `app/blueprints/couriers/routes.py`:
  ```python
  logger.info(f'Created new courier: {courier.name} ({courier.phone})')
  logger.error(f'Error creating courier: {str(e)}')
  ```
- No structured logging (key-value pairs) currently used

## Comments

**When to Comment:**
- Test file docstrings document test coverage scope (see `tests/unit/test_order_service.py` header)
- Test names are sufficiently descriptive; inline comments rare
- Service functions include brief docstrings explaining behavior
- Constants with non-obvious meaning get inline explanation

**JSDoc/TSDoc:**
- Not used (Python project, not TypeScript)
- Docstrings follow implicit convention: first line is brief, complex logic has inline comments
- Test file headers include structured comments describing what's tested and known bugs (with `xfail` markers)

**Example from test file:**
```python
"""
Tests for app/services/order_service.py

Covers:
- get_or_create_client: unknown instagram → (None, error)
- create_order_and_deliveries:
    * creates exactly 1 Order + 1 Delivery
    * is_pickup=True → delivery.street is None

BUG stubs (xfail):
- BUG-03: past delivery_date not rejected
- BUG-04: time_from > time_to not rejected
"""
```

## Function Design

**Size:**
- Route handlers in blueprints: typically 50-300 lines (e.g., `orders_list()` is ~80 lines)
- Service functions: 30-100 lines, with complex logic extracted to helpers
- Test functions: 5-20 lines (one assertion per test, setup in fixtures)

**Parameters:**
- Service functions use keyword args for optional parameters: `search_clients(q=None, sub_filter=None, page=1, per_page=28)`
- Route handlers extract `request.args` or `request.form` explicitly at function start
- Form-like dict objects used in tests implement `.getlist()` for multi-value fields

**Return Values:**
- Services: return tuple `(result, error)` or single result with error handling inside
- Routes: return `render_template()`, `redirect()`, `jsonify()`, or Flask Response
- Query functions return ORM objects or lists of ORM objects
- Pagination helpers return tuple: `(paginated_items, has_next_page)` (see `paginate_orders()`)

## Module Design

**Exports:**
- Services import specific functions: `from app.services.order_service import get_or_create_client, create_order_and_deliveries`
- Blueprint modules export `bp` or `{name}_bp` variable: `orders_bp`, `clients_bp`
- No wildcard imports observed; explicit imports maintain clarity

**Barrel Files:**
- `app/blueprints/{feature}/__init__.py` typically exports blueprint: `from app.blueprints.orders.routes import orders_bp`
- No index files used to re-export model classes; models imported directly
- Service layer has no barrel file; functions imported explicitly per-use

## Database Access

**Query Style:**
- SQLAlchemy ORM via Flask-SQLAlchemy (e.g., `Order.query.filter_by()`, `Client.query.first()`)
- Joins explicitly constructed: `.join()` with relationship or explicit condition
- Eager loading via `joinedload()` for performance (see `app/services/order_service.py:98`)
- Query filtering using method chaining: `query.filter().filter().order_by().all()`

**Transactions:**
- `db.session.add()` for single objects, `db.session.add_all()` for lists
- `db.session.flush()` used to get ID before commit (see `app/services/order_service.py:61`)
- `db.session.commit()` at end of transaction
- No explicit transaction management (rollback) in application code

## Model Relationships

**Foreign Keys:**
- Explicit FK declarations: `client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False, index=True)`
- Backref relationships: `orders = db.relationship('Order', backref='client', lazy=True)` in `Client` model
- Late binding for circular imports: `subscription_id` references `'subscription'` string when needed

**Timestamps:**
- Fields: `created_at` type `db.Date` with default `datetime.date.today` or explicit datetime
- No audit fields (created_by, updated_by) used
- Delivery has `delivered_at` timestamp set on first completion

## Testing Patterns

- See `TESTING.md` for comprehensive testing conventions

---

*Convention analysis: 2026-04-02*
