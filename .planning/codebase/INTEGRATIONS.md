# External Integrations

**Analysis Date:** 2026-04-02

## APIs & External Services

**Route Optimization:**
- Service: Custom route optimization API (configurable via `ROUTE_OPTIMIZER_URL`)
  - What it's used for: Multi-stop delivery route planning and optimization, distance/time calculations
  - SDK/Client: `requests` library (HTTP POST/GET)
  - Implementation: `app/services/route_optimizer_service.py`
  - Auth: API key via `X-API-Key` header (from `OPTIMIZER_API_KEY` env var)
  - Endpoints:
    - `POST /api/optimize/json` - Synchronous JSON-based route optimization
    - `POST /api/optimize` - Async CSV-based route optimization
    - `GET /api/jobs/{job_id}` - Job status polling for async operations
  - Features: Supports delivery time windows, handles infeasibility errors, CSV export of results

## Data Storage

**Databases:**
- PostgreSQL 15 (production/Docker)
  - Connection: `postgresql://kvitkova_user:[password]@postgres:5432/kvitkova_crm`
  - Client: psycopg2-binary (via SQLAlchemy ORM)
  - ORM: Flask-SQLAlchemy
  - Tables: `order`, `delivery`, `client`, `courier`, `certificates`, `user`, `roles`, `delivery_routes`, `prices`, `settings`, `subscription`, `transaction`
  - Migrations: Alembic (Flask-Migrate)

- SQLite (testing only)
  - Connection: `sqlite:///:memory:` (in-memory for test suite)
  - Used in: TestingConfig

**File Storage:**
- Local filesystem only
  - Log files: `/app/logs/` (Telegram bot logs, application logs)
  - Instance data: `/app/instance/` (Flask instance folder for session data, uploads)
  - Database backups: Via script `scripts/database_backup.py` (PostgreSQL dump to local files)

**Caching:**
- Database-backed caching only
  - Route optimization results cached in `DeliveryRoute.cached_result_json` and `cached_at` fields
  - Cache cleanup: Auto-cleanup of results older than 7 days, runs once per day
  - No Redis or Memcached detected

## Authentication & Identity

**Auth Provider:**
- Custom Flask-Login implementation
  - User model: `app/models/user.py`
  - Role-based access control: `admin`, `manager`, `florist`, `courier`
  - Password hashing: Werkzeug (via Flask-Login)
  - Session storage: Filesystem-based

**Telegram Integration (Courier Authentication):**
- Telegram contact sharing for courier verification
  - Handlers: `app/telegram_bot/handlers.py` (CourierHandlers)
  - Verification flow: Phone number extraction from Telegram contact message
  - Chat ID storage: `Courier.telegram_chat_id` field

## Monitoring & Observability

**Error Tracking:**
- Not detected - no Sentry, Rollbar, or similar service configured

**Logs:**
- Standard Python logging module
- Telegram bot logs to `/app/logs/telegram_bot.log`
- Flask application logs to console (stdout in Docker)
- No centralized log aggregation (ELK, Datadog, etc.) detected

**Health Checks:**
- Docker Compose healthchecks configured:
  - Web service: `curl -f http://localhost:8000/` (30s interval, 10s timeout, 3 retries)
  - PostgreSQL: `pg_isready -U kvitkova_user -d kvitkova_crm` (10s interval, 5s timeout, 5 retries, 30s start period)

## CI/CD & Deployment

**Hosting:**
- Docker Compose (local/self-hosted deployment)
- Services: web (Gunicorn), postgres (15-alpine), telegram-bot (polling)
- Port mapping: 8002 → 8000 (web), 5432 (postgres)

**CI Pipeline:**
- GitHub Actions workflow: `.github/workflows/tests.yml`
  - Test environment: SQLite in-memory (`sqlite:///:memory:`)
  - Runner: Ubuntu (default)
  - No production deployment pipeline detected (manual Docker Compose)

## Environment Configuration

**Required env vars:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot API token (required for bot functionality)
- `DATABASE_URL` - PostgreSQL connection string
- `ROUTE_OPTIMIZER_URL` - Base URL for route optimization API (if using route optimization)
- `OPTIMIZER_API_KEY` - API key for route optimizer (optional, if API requires auth)
- `DEPOT_ADDRESS` - Default depot address for route calculations
- `SECRET_KEY` - Flask session/CSRF secret key

**Optional env vars:**
- `POSTGRES_PASSWORD` - Override default postgres password (default: `kvitkova_password`)
- `ADMIN_USERNAME` - Initial admin user username (default: `admin`)
- `ADMIN_EMAIL` - Initial admin user email (default: `admin@kvitkovapovnya.com`)
- `ADMIN_PASSWORD` - Initial admin user password (no default, must be set for Docker admin creation)
- `TELEGRAM_WEBHOOK_URL` - Webhook URL for Telegram (optional, currently using polling)
- `TELEGRAM_WEBHOOK_SECRET` - Webhook secret (optional, for webhook mode)
- `TELEGRAM_NOTIFICATIONS_ENABLED` - Enable/disable Telegram notifications (default: `true`)
- `FLASK_ENV` - Environment: `development`, `production`, `testing` (default: `production` in Docker)
- `FLASK_APP` - Entry point: `run.py`

**Secrets location:**
- `.env` file (git-ignored)
- Environment variables in `docker-compose.yml` (overrides `.env`)
- Admin credentials passed at runtime in Docker

## Webhooks & Callbacks

**Incoming:**
- Telegram bot updates: via polling (long-polling from Telegram API)
- Route optimizer: No webhooks detected, polling-based job status checks (`GET /api/jobs/{job_id}`)

**Outgoing:**
- Telegram notifications: `app/telegram_bot/notification_service.py`
  - Method: Async send via `Application.bot.send_message()`
  - Trigger: Manual from delivery assignment or scheduled notifications
  - Receives: Delivery information, courier chat ID, delivery dates/times

## Database Backup & Recovery

**Backup Script:**
- Location: `scripts/database_backup.py`
- Method: `pg_dump` to local SQL files
- Rotation: Keeps last 7 backups
- Location: `/backup/` directory

**Restore:**
- Manual via `psql` or `pg_restore`
- Using `--clean --if-exists` flags for safe restoration to existing databases

---

*Integration audit: 2026-04-02*
