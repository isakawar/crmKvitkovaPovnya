# Codebase Structure

**Analysis Date:** 2026-04-02

## Directory Layout

```
/Users/vladbilobrov/Develop/crmKvitkovaPovnya/
├── app/                          # Flask application root
│   ├── __init__.py               # App factory (create_app), blueprint registration, global filters
│   ├── config.py                 # Configuration classes (Dev, Prod, Test)
│   ├── extensions.py             # Flask extensions (db, migrate, login_manager)
│   ├── blueprints/               # Route handlers grouped by domain
│   │   ├── auth/                 # Authentication routes (/auth/login, /auth/logout)
│   │   ├── orders/               # Order CRUD and list (/orders, /orders/new, /orders/edit)
│   │   ├── clients/              # Client management (/clients, /clients/new)
│   │   ├── subscriptions/        # Subscription management (/subscriptions)
│   │   ├── couriers/             # Courier management (/couriers)
│   │   ├── certificates/         # Gift certificates (/certificates)
│   │   ├── dashboard/            # Home page and dashboard (/)
│   │   ├── routes/               # Delivery route optimization (/routes, /route-generator)
│   │   ├── florist/              # Florist-only page (/florist)
│   │   ├── reports/              # Reports and analytics (/reports)
│   │   ├── import_csv/           # Data import (/import)
│   │   ├── transactions/         # Client balance transactions (/transactions)
│   │   ├── settings/             # App settings configuration (/settings)
│   │   └── distribution/         # Distribution list (minimal)
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── __init__.py           # Model exports
│   │   ├── order.py              # Order model (order table)
│   │   ├── delivery.py           # Delivery model (delivery table)
│   │   ├── subscription.py       # Subscription model (subscription table)
│   │   ├── client.py             # Client model (client table)
│   │   ├── courier.py            # Courier model (courier table)
│   │   ├── delivery_route.py     # DeliveryRoute, RouteDelivery models (delivery_routes, route_deliveries tables)
│   │   ├── certificate.py        # Certificate model (certificates table)
│   │   ├── user.py               # User, Role models (user, roles, user_roles tables)
│   │   ├── price.py              # Price model (prices table)
│   │   ├── settings.py           # Settings model (settings table, singleton-like)
│   │   ├── transaction.py        # Transaction model (transactions table)
│   │   └── recipient_phone.py    # RecipientPhone model (recipient_phones table)
│   ├── services/                 # Business logic layer
│   │   ├── order_service.py      # Order creation, updates, queries (core business logic)
│   │   ├── subscription_service.py # Subscription creation, renewal, draft management
│   │   ├── delivery_service.py   # Delivery grouping, financial week calculations
│   │   ├── client_service.py     # Client CRUD
│   │   ├── courier_service.py    # Courier creation
│   │   ├── csv_import_service.py # CSV parsing and bulk import
│   │   ├── reports_service.py    # Analytics, revenue, performance reports
│   │   └── route_optimizer_service.py # External Route Optimizer API integration
│   ├── telegram_bot/             # Telegram bot integration
│   │   ├── __init__.py           # TelegramBot class initialization
│   │   └── (handlers for courier notifications)
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── layout.html           # Base template (sidebar, topbar, Bootstrap setup)
│   │   ├── macros.html           # Reusable template macros (render_toast, render_alerts)
│   │   ├── auth/
│   │   │   └── login.html        # Login page
│   │   ├── orders/
│   │   │   ├── list.html         # Order list with filters and deliveries table
│   │   │   ├── form.html         # Single-page form for order/subscription
│   │   │   ├── _composer_modal.html  # Modal for creating/editing orders
│   │   │   └── _composer_script.html # JS logic for composer (40KB, form state management)
│   │   ├── subscriptions/
│   │   │   ├── list.html         # Subscription list with draft and active tabs
│   │   │   └── (modals embedded in list.html)
│   │   ├── clients/
│   │   │   ├── list.html         # Client list with search
│   │   │   └── modal.html        # Client create/edit modal
│   │   ├── couriers/
│   │   │   └── list.html         # Courier list and creation form
│   │   ├── certificates/
│   │   │   ├── list.html         # Certificate list
│   │   │   ├── _create_modal.html
│   │   │   └── _detail_modal.html
│   │   ├── dashboard/
│   │   │   └── index.html        # Dashboard with stats and latest orders
│   │   ├── routes/
│   │   │   └── list.html         # Delivery routes list with optimization UI
│   │   ├── reports/
│   │   │   └── index.html        # Reports and analytics dashboard
│   │   ├── florist/
│   │   │   └── list.html         # Florist-only delivery assignments
│   │   ├── transactions/
│   │   │   └── list.html         # Client transaction history
│   │   ├── settings/
│   │   │   └── index.html        # Settings: cities, sizes, delivery types, prices
│   │   └── import_csv/
│   │       └── kvitkovapovnya.html # CSV import form
│   ├── static/                   # Frontend assets
│   │   ├── css/
│   │   │   ├── src/
│   │   │   │   └── input.css     # Tailwind source with @layer components
│   │   │   └── main.css          # Compiled Tailwind CSS (do not edit)
│   │   ├── js/
│   │   │   └── clients.js        # Reusable JavaScript utilities
│   │   └── img/
│   │       └── favicon.ico
│   └── utils/                    # Utility functions (reserved, currently minimal)
├── migrations/                   # Alembic database migrations
│   ├── versions/                 # Migration files (one per schema change)
│   ├── env.py                    # Alembic environment configuration
│   └── alembic.ini               # Alembic config file
├── tests/                        # Pytest test suite
│   ├── conftest.py               # Pytest fixtures and configuration
│   ├── test_orders.py            # Order tests
│   ├── test_subscriptions.py     # Subscription tests
│   ├── test_clients.py           # Client tests
│   └── (other test files)
├── scripts/                      # Utility scripts
│   ├── seed_settings.py          # Initialize Settings table (cities, sizes, delivery types)
│   ├── database_backup.py        # Backup PostgreSQL database
│   └── (other scripts)
├── docs/                         # Documentation
│   └── (architecture, API docs)
├── run.py                        # Flask development entry point
├── requirements.txt              # Python dependencies
├── package.json                  # Node.js dependencies (Tailwind)
├── tailwind.config.js            # Tailwind CSS configuration
├── docker-compose.yml            # Production-like Docker setup
├── Dockerfile                    # Flask app container
├── entrypoint.sh                 # Docker entrypoint (runs migrations)
├── alembic.ini                   # Alembic initialization config
├── CLAUDE.md                     # Developer instructions (this file)
├── .env                          # Environment variables (DO NOT COMMIT - contains secrets)
├── .gitignore                    # Ignored files
└── VERSION                       # Current version string
```

## Directory Purposes

**app/blueprints/**
- Purpose: Organize HTTP route handlers by domain/feature
- Pattern: Each blueprint is a subdirectory with `__init__.py` (creates Blueprint), `routes.py` (handlers)
- Registration: All blueprints imported and registered in `app/__init__.py`

**app/models/**
- Purpose: Define SQLAlchemy ORM models representing database tables
- Pattern: One model per file or grouped by domain
- Imports: All models exported from `__init__.py`, imported throughout services and routes

**app/services/**
- Purpose: Implement business logic separate from HTTP handlers
- Pattern: Service functions take models and form data, return results, raise exceptions
- Organization: One service per domain (order_service, client_service, etc.)

**app/templates/**
- Purpose: Jinja2 HTML templates rendered by routes
- Pattern: Mirror blueprint structure under `templates/`, inherit from `layout.html`
- Modals: Named with leading underscore (`_modal.html`, `_script.html`) when included in parent

**app/static/css/src/**
- Purpose: Source Tailwind CSS configuration
- Pattern: Edit `input.css`, run `npm run build` to compile to `main.css`
- Build: Tailwind watches `app/templates/` for class names, outputs to `app/static/css/main.css`

**migrations/versions/**
- Purpose: Database schema evolution as Python files
- Pattern: Alembic auto-generates or manually written, one file per migration
- Naming: Auto-timestamped format `YYYYMMDDHHMMSS_description.py`

## Key File Locations

**Entry Points:**
- `run.py`: Development server entry, calls `create_app()` and runs Flask dev server
- `app/__init__.py`: App factory, blueprint registration, global middleware/filters
- `app/config.py`: Configuration per environment (Dev, Prod, Test)

**Configuration:**
- `.env`: Environment variables (DATABASE_URL, TELEGRAM_BOT_TOKEN, ROUTE_OPTIMIZER_URL, SECRET_KEY) - **DO NOT COMMIT**
- `tailwind.config.js`: Tailwind CSS customizations (colors, spacing, plugins)
- `alembic.ini`: Alembic migration configuration

**Core Logic:**
- `app/services/order_service.py`: Core order and delivery creation logic (40+ functions)
- `app/services/subscription_service.py`: Subscription management (30+ functions)
- `app/services/delivery_service.py`: Delivery queries and grouping by date
- `app/blueprints/orders/routes.py`: Order list, create, edit endpoints (main page)

**Database:**
- `app/models/order.py`: Order ORM model (order table)
- `app/models/delivery.py`: Delivery ORM model (delivery table)
- `app/models/subscription.py`: Subscription ORM model (subscription table)
- `app/extensions.py`: SQLAlchemy db instance

**Authentication:**
- `app/blueprints/auth/routes.py`: Login/logout endpoints
- `app/models/user.py`: User, Role models with permission system

**Frontend:**
- `app/templates/layout.html`: Base HTML template with sidebar, topbar, Bootstrap
- `app/templates/orders/_composer_modal.html`: Large order creation modal (30KB)
- `app/templates/orders/_composer_script.html`: JavaScript for composer form (40KB)
- `app/static/css/main.css`: Compiled Tailwind CSS (read-only, auto-generated)

**Testing:**
- `tests/conftest.py`: Pytest configuration and fixtures
- `tests/test_orders.py`: Order creation and filtering tests

## Naming Conventions

**Files:**
- Python files: `snake_case.py` (e.g., `order_service.py`, `delivery_route.py`)
- Template files: `snake_case.html` (e.g., `orders_list.html`), prefixed with `_` for included partials (e.g., `_composer_modal.html`)
- CSS files: `input.css` (source), `main.css` (compiled, do not edit)

**Directories:**
- Feature/domain directories: `lowercase` (e.g., `orders`, `clients`, `subscriptions`)
- Blueprint directories: Same as route prefix without leading slash (e.g., `/orders` → `blueprints/orders/`)

**Classes:**
- Model classes: `PascalCase` (e.g., `Order`, `Client`, `Subscription`, `DeliveryRoute`)
- Blueprint instances: `snake_case_bp` (e.g., `orders_bp`, `clients_bp`)

**Functions:**
- Route handlers: `snake_case` (e.g., `orders_list()`, `create_order()`)
- Service functions: `snake_case` (e.g., `create_order_and_deliveries()`, `get_or_create_client()`)

**Variables:**
- Django-style imports: `from app.models import Order` (PascalCase for models)
- Form data: Accessed via `form.get('key')` or `form['key']` (form key names match HTML input names)
- Database columns: `snake_case` (e.g., `order.recipient_name`, `delivery.delivery_date`)

**HTML/Templates:**
- CSS classes: Tailwind utilities (e.g., `.flex`, `.gap-3`) + custom components prefixed by domain
  - Order-related: `.order-*` (e.g., `.order-panel`, `.order-field`)
  - Client-related: `.client-*`
  - Badges/tags: `.tag-*` (e.g., `.tag-hard`, `.tag-pickup`)
- Form input names: Match Python field names (e.g., `<input name="recipient_name">` → `form['recipient_name']`)
- Modal IDs: `#{domain}Modal` or `#{domain}{action}Modal` (e.g., `#orderModal`, `#clientCreateModal`)

## Where to Add New Code

**New Feature (e.g., new entity like "Payment"):**

1. **Model:** Create `app/models/payment.py` defining Payment class with SQLAlchemy columns, relationships
2. **Service:** Create `app/services/payment_service.py` with functions like `create_payment()`, `get_payments()`
3. **Routes:** Create `app/blueprints/payments/` with `__init__.py` (creates blueprint) and `routes.py` (handlers)
4. **Templates:** Create `app/templates/payments/` with `list.html`, `_create_modal.html`, etc.
5. **Migration:** Run `flask db migrate -m "Add payment model"` to auto-generate migration, review, then `flask db upgrade`
6. **Register Blueprint:** Add import and `app.register_blueprint()` in `app/__init__.py`

**New Route Endpoint (e.g., new action on Orders):**

1. Add handler function to `app/blueprints/orders/routes.py` with `@orders_bp.route('/orders/new-action', methods=['GET', 'POST'])`
2. Call service functions or query models as needed
3. Render template or return JSON response
4. Add navigation link in `app/templates/layout.html` sidebar if user-facing

**New Template Component (e.g., new modal):**

1. Create `app/templates/{domain}/_component_name.html` extending nothing (or include in parent)
2. Include via `{% include 'domain/_component_name.html' %}`
3. If using new Tailwind classes, add to `app/static/css/src/input.css` via `@layer components`
4. Run `npm run build` to compile CSS (production) or use `npm run dev` for watch mode

**New Service Function (e.g., bulk operation):**

1. Add to appropriate service file (e.g., `app/services/order_service.py`)
2. Start with docstring explaining inputs, outputs, exceptions
3. Use session.flush() for intermediate states, session.commit() at end
4. Raise descriptive exceptions (ValueError, etc.) on validation failures
5. Log significant operations with `logger.info()`

**New Database Field:**

1. Add column to model class in `app/models/` (e.g., `app/models/order.py`)
2. Run `flask db migrate -m "Add field to Order"` to auto-detect and generate migration
3. Review generated migration file in `migrations/versions/`
4. Run `flask db upgrade` to apply to database
5. Update forms/templates to display/input new field

**New Test:**

1. Add test file to `tests/test_{feature}.py` or add test to existing file
2. Use `conftest.py` fixtures (app, client, db) for setup
3. Follow pattern: setup → call function → assert results
4. Run `pytest tests/test_file.py` to test

## Special Directories

**migrations/versions/:**
- Purpose: Store Alembic migration files
- Generated: Run `flask db migrate -m "description"` to auto-generate based on model changes
- Committed: Yes, required for schema evolution tracking
- Manual edits: Yes, if auto-generation misses something (e.g., adding a database constraint)

**data/:**
- Purpose: Store raw data files (imports, backups)
- Generated: Yes, by scripts and manual uploads
- Committed: No, large files not tracked in git

**logs/:**
- Purpose: Store application logs
- Generated: Yes, by logging handlers at runtime
- Committed: No, sensitive information

**.planning/codebase/:**
- Purpose: Store codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes, by GSD mapper tools
- Committed: Yes, useful for team reference

**node_modules/:**
- Purpose: Node.js packages for Tailwind CSS
- Generated: Yes, by `npm install`
- Committed: No, generated from package-lock.json

**instance/:**
- Purpose: Flask instance folder (optional config, session data)
- Generated: Yes, at runtime
- Committed: No

---

*Structure analysis: 2026-04-02*
