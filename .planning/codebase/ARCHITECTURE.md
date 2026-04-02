# Architecture

**Analysis Date:** 2026-04-02

## Pattern Overview

**Overall:** Layered 3-tier MVC architecture with Blueprint-based routing and service-oriented business logic.

**Key Characteristics:**
- Flask blueprints organize routes by domain (orders, clients, couriers, certificates, etc.)
- SQLAlchemy ORM with explicit data models defines the data layer
- Service layer (`app/services/`) encapsulates business logic separate from routes
- Jinja2 templates render HTML with form handling via Flask request context
- AJAX endpoints return JSON for dynamic UI updates
- Telegram bot integration for courier notifications and route management

## Layers

**Presentation (View):**
- Purpose: Render HTML templates and handle AJAX JSON responses
- Location: `app/templates/`, `app/blueprints/*/routes.py` (route handlers)
- Contains: Jinja2 templates extending `layout.html`, form handlers, AJAX endpoints
- Depends on: Service layer for business logic, Models for data access
- Used by: Web browsers, Telegram bot webhooks

**Application (Controller):**
- Purpose: Route HTTP requests to handlers, manage request/response flow, call service layer
- Location: `app/blueprints/*/routes.py`
- Contains: Route handlers decorated with `@blueprint.route()`, AJAX endpoint handlers, form validation
- Depends on: Service layer functions, Models for queries, Flask request context
- Used by: Presentation layer (templates render routes via `url_for()`)

**Business Logic (Service):**
- Purpose: Implement domain-specific operations, coordinate models, handle complex workflows
- Location: `app/services/`
- Contains: Order creation/updates, subscription management, delivery routing, reports generation, data import
- Depends on: Models (ORM queries), Extensions (db), External APIs (Route Optimizer, Telegram)
- Used by: Routes, Telegram bot, scheduled jobs (APScheduler)

**Data (Model):**
- Purpose: Define database schema and relationships, provide ORM interface
- Location: `app/models/`
- Contains: SQLAlchemy model classes (Order, Delivery, Client, Subscription, User, etc.), relationships
- Depends on: Flask-SQLAlchemy extension, PostgreSQL type system
- Used by: Service layer queries, Routes for direct access, Migrations

**Infrastructure (Extensions):**
- Purpose: Initialize and configure Flask extensions
- Location: `app/extensions.py` (db, migrate, login_manager)
- Contains: SQLAlchemy instance, Flask-Migrate instance, Flask-Login manager
- Depends on: Flask, flask-sqlalchemy, flask-migrate, flask-login
- Used by: All layers for database access, authentication, migrations

## Data Flow

**Order Creation Flow:**

1. User submits order form via `POST /orders/new`
2. Routes handler `create_order()` receives request, validates form data
3. Calls `order_service.create_order_and_deliveries(client, form)`
4. Service creates `Order` record, creates `Delivery` records (1 for one-time, multiple for subscriptions)
5. Service creates `RecipientPhone` records for additional phone numbers
6. Session committed to PostgreSQL
7. Delivery records trigger subscriber notifications (optional)
8. Template renders success response, redirects to order list

**Delivery Routing Flow:**

1. User views `/routes` page, selects delivery date
2. Route handler calls `delivery_service.get_deliveries(filters...)`
3. Service queries `Delivery` table, returns grouped by date
4. User initiates route optimization via AJAX `POST /route-generator`
5. Routes handler submits deliveries to external Route Optimizer API (CSV)
6. Receives optimized route JSON, stores in `DeliveryRoute.cached_result_json`
7. Creates `RouteDelivery` records mapping deliveries to route stops (order sequence)
8. Telegram bot receives route, shows courier the stop sequence and estimated times

**Subscription Management Flow:**

1. User creates subscription via composer modal with `delivery_type='Weekly|Monthly|Bi-weekly'`
2. Routes handler calls `subscription_service.create_subscription()`
3. Service creates `Subscription` record with `type`, `status='active'`, `delivery_day`
4. Service auto-generates 4 `Order` records with `sequence_number=1-4`
5. Each Order triggers Delivery creation
6. Subscription fulfillment scheduled via APScheduler or manual order creation
7. Client balance tracked via `Client.credits` and `Transaction` records

**State Management:**

- **Order state:** Captured in `Order.delivery_date`, `Order.created_at`, denormalized in `Delivery` for fast queries
- **Delivery state:** Status field (`'Очікує'`, `'Доставлено'`, `'Скасовано'`) tracks fulfillment, `courier_id` tracks assignment
- **Route state:** `DeliveryRoute.status` tracks lifecycle (`draft` → `sent` → `accepted` → `completed`)
- **Subscription state:** `Subscription.status` tracks active/completed/cancelled, `is_extended` tracks renewals
- **Authentication state:** Flask-Login manages session via `current_user` context variable
- **Client balance:** `Client.credits` tracks prepaid amount, `Transaction` table records all credit movements

## Key Abstractions

**Service Functions (Business Operations):**
- Purpose: Encapsulate workflows, abstract database queries, coordinate side effects
- Examples: `app/services/order_service.py`, `app/services/subscription_service.py`, `app/services/delivery_service.py`
- Pattern: Take domain objects and form data, return created/updated models, raise exceptions on validation errors

**Models (Domain Objects):**
- Purpose: Represent core entities and relationships
- Examples: `Order`, `Delivery`, `Subscription`, `Client`, `Courier`, `DeliveryRoute`, `User`
- Pattern: SQLAlchemy Model classes with relationships defining joins, primary keys are auto-increment integers

**Blueprints (Domain-Grouped Routes):**
- Purpose: Namespace and organize related endpoints by domain
- Examples: `app/blueprints/orders/`, `app/blueprints/clients/`, `app/blueprints/routes/`
- Pattern: Each blueprint has `__init__.py` creating Blueprint instance, `routes.py` defining handlers

**External Services:**
- Route Optimizer API: `app/services/route_optimizer_service.py` - submits CSV of deliveries, receives optimized route JSON
- Telegram Bot: `app/telegram_bot/` - webhooks receive courier route confirmations, sends notifications
- Nova Poshta (parcel service): Referenced in delivery_method but integration not implemented

## Entry Points

**Web Application:**
- Location: `run.py`
- Triggers: `python run.py` (development) or Gunicorn (production)
- Responsibilities: Instantiate Flask app via `create_app()`, run development server or pass to WSGI

**Flask App Factory:**
- Location: `app/__init__.py` `create_app()`
- Triggers: Called by `run.py` or WSGI server
- Responsibilities: Initialize extensions (db, migrate, login_manager), register blueprints, set up filters and error handlers, configure Telegram bot

**Blueprint Routes:**
- Location: `app/blueprints/{domain}/routes.py`
- Triggers: HTTP requests to registered paths
- Responsibilities: Parse request data, call services, render templates or return JSON

**Telegram Bot Webhooks:**
- Location: `app/telegram_bot/` via Flask route
- Triggers: Telegram API sends updates when user sends message
- Responsibilities: Parse Telegram updates, call services to update delivery status, send notifications

**APScheduler Jobs:**
- Location: Configured in `app/services/subscription_service.py` and route handling code
- Triggers: Scheduled times (e.g., daily subscription fulfillment check)
- Responsibilities: Create new orders for active subscriptions, update statuses

**Database Migrations:**
- Location: `migrations/versions/` Alembic migration files
- Triggers: `flask db upgrade` command on startup (Docker entrypoint)
- Responsibilities: Create tables, add columns, add constraints, manage schema evolution

## Error Handling

**Strategy:** Try-catch in routes, log errors, return user-friendly messages via flash() or JSON error response

**Patterns:**

- **Form validation:** Check form fields in route handler before calling service, return form with errors or flash error message
- **Business logic errors:** Service functions raise exceptions (ValueError, RouteOptimizerError), routes catch and flash error message
- **Database errors:** SQLAlchemy rollbacks session on IntegrityError, routes catch and return generic error message
- **External API errors:** Route optimizer service catches requests exceptions, returns error dict, routes check for errors and flash message
- **Authentication:** `@login_required` decorator redirects to login; before_request checks user type for florist restrictions

## Cross-Cutting Concerns

**Logging:** 
- Python `logging` module imported in service files
- Format: Logger per module (`logger = logging.getLogger(__name__)`)
- Usage: Log significant operations (`create_order`, `optimize_route`), warnings (parsing errors), errors (API failures)

**Validation:**
- Form-level: In routes, check required fields, parse dates, validate phone format
- Service-level: Services validate business rules (subscription size required, delivery date must be future, etc.)
- Database-level: SQLAlchemy constraints (NOT NULL, UNIQUE), foreign keys enforce referential integrity

**Authentication:**
- Global protection: `before_request` in `app/__init__.py` checks `current_user.is_authenticated`
- Role-based access: User.roles relationship defines permissions, florist role restricts to /florist routes
- Session: Flask-Login manages session cookie, load_user() loader fetches User from database

**Authorization:**
- Role permissions: `ROLE_PERMISSIONS` dict defines capabilities per role (admin, manager, florist)
- Route-level: Florist users redirected to /florist only via `before_request` check
- Feature-level: Some forms/modals conditionally rendered based on user role

**Transactions:**
- Default: SQLAlchemy auto-commits session.commit() in routes
- Complex operations: Service functions use session.flush() for intermediate states, commit once at end
- Rollback: On exceptions, before_request cleanup catches and calls db.session.rollback()

---

*Architecture analysis: 2026-04-02*
