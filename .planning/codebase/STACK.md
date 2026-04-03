# Technology Stack

**Analysis Date:** 2026-04-02

## Languages

**Primary:**
- Python 3.12 - Backend application server (Flask)

**Secondary:**
- JavaScript - Frontend interactivity (Tailwind CSS, client-side logic)
- HTML/Jinja2 - Template rendering for web interface
- SQL - Database queries via SQLAlchemy ORM

## Runtime

**Environment:**
- Python 3.12 slim (Docker image: `python:3.12-slim`)
- Flask development server: `run.py` (debug=True, port 5055)
- Production WSGI: Gunicorn 4 workers, timeout 140s

**Package Manager:**
- pip (Python)
- npm (Node.js) - for Tailwind CSS compilation only

## Frameworks

**Core:**
- Flask - Web application framework
- Flask-SQLAlchemy 3.x - ORM and database abstraction
- Flask-Migrate / Alembic - Database migrations
- Flask-Login 0.6.3 - User authentication and session management
- Flask-WTF - Form handling and CSRF protection

**Frontend/Styling:**
- Tailwind CSS 3.4.0 - Utility-first CSS framework (watch: `npm run dev`, build: `npm run build`)
- Bootstrap 5.3.2 - UI components
- Bootstrap Icons - Icon library

**Bot/Integration:**
- python-telegram-bot 20.7 - Telegram Bot API client with async support
- APScheduler 3.10.4 - Background task scheduling (imported but not actively used in current codebase)

**Build/Dev:**
- npm (Tailwind CLI only)
- Docker Compose - Container orchestration

## Key Dependencies

**Critical:**
- psycopg2-binary - PostgreSQL database adapter for Python
- SQLAlchemy (via Flask-SQLAlchemy) - ORM for database operations
- python-telegram-bot 20.7 - Telegram bot framework with polling and webhook support
- requests - HTTP client library for external API calls

**Infrastructure:**
- python-dotenv - Environment variable loading from `.env` files
- Gunicorn - Production WSGI HTTP server
- Flask-WTF - Form security and CSRF token handling

**Testing:**
- pytest - Test runner and framework

## Configuration

**Environment:**
- `.env` file (loaded via `python-dotenv`)
- Flask config classes: `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`
- Environment variables via `app/config.py`:
  - `DATABASE_URL` - PostgreSQL connection string
  - `TELEGRAM_BOT_TOKEN` - Telegram bot API token
  - `TELEGRAM_WEBHOOK_URL` - Webhook URL for Telegram (optional, polling used in production)
  - `ROUTE_OPTIMIZER_URL` - External route optimization API base URL
  - `OPTIMIZER_API_KEY` - API key for route optimizer
  - `DEPOT_ADDRESS` - Default depot address for route optimization
  - `SECRET_KEY` - Flask session/CSRF secret key
  - `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` - Initial admin user (Docker only)

**Build:**
- `tailwind.config.js` - Tailwind CSS configuration (scans `app/templates/**/*.html`, `app/static/js/**/*.js`)
- `package.json` - npm scripts for CSS compilation
- `Dockerfile` - Multi-stage Python image build
- `docker-compose.yml` - Service orchestration (web, postgres, telegram-bot)
- `entrypoint.sh` - Database migration and app startup script

## Platform Requirements

**Development:**
- Python 3.12 (local)
- PostgreSQL 15+ (or local/Docker)
- Node.js (for Tailwind CSS compilation)
- Git

**Production:**
- Docker & Docker Compose
- PostgreSQL 15 (containerized as `postgres:15-alpine`)
- Linux host (healthchecks use `curl` and `pg_isready`)
- Ports: 8002 (web), 5432 (postgres)

## Logging

**Approach:**
- Python standard `logging` module
- File logging: `/app/logs/telegram_bot.log` (Telegram bot service)
- Console output to stdout
- Configured in scripts (e.g., `scripts/run_telegram_bot.py`)
- No centralized logging service integration detected

## Session Management

**Session Type:**
- Filesystem-based sessions (Flask default, `SESSION_TYPE='filesystem'`)
- Session duration: 24 hours (`PERMANENT_SESSION_LIFETIME`)
- Remember-me cookie: 24 hours (`REMEMBER_COOKIE_DURATION`)

---

*Stack analysis: 2026-04-02*
