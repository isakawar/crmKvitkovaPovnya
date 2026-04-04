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
    from app.models.ai_log import AIAgentLog  # noqa: ensure table is created

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
    from app.blueprints.ai_agent import ai_agent_bp

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
    app.register_blueprint(ai_agent_bp)

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

    def _create_user(user_type, role_name, role_description):
        import click
        from app.models.user import User, Role

        username = click.prompt('Username')
        if User.query.filter_by(username=username).first():
            click.echo(f'Користувач "{username}" вже існує.')
            return

        email = click.prompt('Email')
        if User.query.filter_by(email=email).first():
            click.echo(f'Email "{email}" вже використовується.')
            return

        password = click.prompt('Password', hide_input=True, confirmation_prompt=True)

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=role_description)
            db.session.add(role)
            db.session.flush()

        user = User(username=username, email=email, user_type=user_type, is_active=True)
        user.set_password(password)
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Створено {user_type} "{username}".')

    @app.cli.command('create-admin')
    def create_admin():
        """Створити адміністратора інтерактивно."""
        _create_user('admin', 'admin', 'Administrator')

    @app.cli.command('ensure-admin')
    def ensure_admin():
        """Створити адміністратора з env змінних (для Docker)."""
        import os
        from app.models.user import User, Role

        username = os.environ.get('ADMIN_USERNAME', 'admin')
        email = os.environ.get('ADMIN_EMAIL', 'admin@kvitkovapovnya.com')
        password = os.environ.get('ADMIN_PASSWORD', '')

        if not password:
            print('ADMIN_PASSWORD not set, skipping admin creation.')
            return

        if User.query.filter_by(username=username).first():
            print(f'Admin "{username}" already exists, skipping.')
            return

        role = Role.query.filter_by(name='admin').first()
        if not role:
            role = Role(name='admin', description='Administrator')
            db.session.add(role)
            db.session.flush()

        user = User(username=username, email=email, user_type='admin', is_active=True)
        user.set_password(password)
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
        print(f'Admin "{username}" created.')

    @app.cli.command('create-florist')
    def create_florist():
        """Створити флориста інтерактивно."""
        _create_user('florist', 'florist', 'Florist')

    version = get_version()
    @app.context_processor
    def inject_version():
        return dict(app_version=version)

    @app.context_processor
    def inject_ai_agent_enabled():
        if not current_user.is_authenticated:
            return dict(ai_agent_enabled=False)
        try:
            from app.models.settings import Settings
            disabled = Settings.query.filter_by(
                type='feature_flag', value='ai_agent_disabled'
            ).first()
            return dict(ai_agent_enabled=disabled is None)
        except Exception:
            return dict(ai_agent_enabled=True)

    @app.route('/changelog')
    def changelog():
        try:
            with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
                content = f.read()
            return Response(content, mimetype='text/plain; charset=utf-8')
        except FileNotFoundError:
            return "Changelog not found", 404

    return app
