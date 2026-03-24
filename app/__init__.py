import os
import datetime as _dt_module
from flask import Flask, render_template, send_file, Response, redirect, url_for, request
from dotenv import load_dotenv
from flask_login import current_user

_last_route_cache_cleanup = None

# Load environment variables from .env file
load_dotenv()
from app.extensions import db, migrate, login_manager
from app.config import Config, DevelopmentConfig
from app.telegram_bot import TelegramBot

def get_version():
    try:
        with open('VERSION', 'r') as f:
            return f.read().strip()
    except:
        return '0.0.0.0'

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Initialize Telegram Bot
    telegram_bot = TelegramBot()
    telegram_bot.init_app(app)
    app.telegram_bot = telegram_bot

    # Register blueprints
    from app.blueprints.orders.routes import orders_bp
    from app.blueprints.clients.routes import clients_bp
    from app.blueprints.couriers.routes import couriers_bp
    from app.blueprints.reports.routes import reports_bp
    from app.blueprints.settings.routes import bp as settings_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.routes.routes import routes_bp
    from app.blueprints.florist.routes import florist_bp
    from app.blueprints.import_csv.routes import import_csv_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.certificates import certificates_bp
    from app.blueprints.transactions import transactions_bp
    from app.blueprints.subscriptions import subscriptions_bp

    app.register_blueprint(orders_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(couriers_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(florist_bp)
    app.register_blueprint(import_csv_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(certificates_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(subscriptions_bp)

    # Cleanup old route cache (раз на добу, старше 7 днів)
    @app.before_request
    def cleanup_route_cache():
        global _last_route_cache_cleanup
        now = _dt_module.datetime.utcnow()
        if _last_route_cache_cleanup and (now - _last_route_cache_cleanup).total_seconds() < 86400:
            return
        _last_route_cache_cleanup = now
        try:
            from app.models.delivery_route import DeliveryRoute
            cutoff = now - _dt_module.timedelta(days=7)
            (DeliveryRoute.query
                .filter(DeliveryRoute.cached_at != None, DeliveryRoute.cached_at < cutoff)
                .update({'cached_result_json': None, 'cached_at': None}, synchronize_session=False))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Захист всіх маршрутів за замовчуванням
    @app.before_request
    def require_login():
        public_endpoints = ['auth.login', 'static', 'changelog']
        if request.endpoint and not current_user.is_authenticated:
            if not any(endpoint == request.endpoint for endpoint in public_endpoints):
                return redirect(url_for('auth.login'))
        # Флорист може заходити тільки на сторінку флориста
        if (current_user.is_authenticated
                and getattr(current_user, 'user_type', None) == 'florist'
                and request.endpoint
                and not request.endpoint.startswith('florist.')
                and not request.endpoint.startswith('auth.')
                and request.endpoint != 'static'):
            return redirect(url_for('florist.florist_routes'))

    # Головна сторінка перенаправляє на список замовлень
    @app.route('/')
    def index():
        return redirect(url_for('dashboard.dashboard_page'))

    from zoneinfo import ZoneInfo
    _kyiv_tz = ZoneInfo('Europe/Kyiv')

    @app.template_filter('kyiv_time')
    def kyiv_time_filter(dt):
        if dt is None:
            return ''
        import datetime as _dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt.astimezone(_kyiv_tz).strftime('%d.%m.%Y %H:%M')

    version = get_version()
    @app.context_processor
    def inject_version():
        return dict(app_version=version)

    @app.route('/changelog')
    def changelog():
        try:
            with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
                content = f.read()
            return Response(content, mimetype='text/plain; charset=utf-8')
        except FileNotFoundError:
            return "Changelog not found", 404

    return app
