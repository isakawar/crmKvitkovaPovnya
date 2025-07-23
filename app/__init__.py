import os
from flask import Flask, render_template, send_file, Response, redirect, url_for, request
from dotenv import load_dotenv
from flask_login import current_user

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
    from app.blueprints.deliveries.routes import deliveries_bp
    from app.blueprints.distribution.routes import distribution_bp
    from app.blueprints.reports.routes import reports_bp
    from app.blueprints.settings.routes import bp as settings_bp
    from app.blueprints.auth import bp as auth_bp

    app.register_blueprint(orders_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(couriers_bp)
    app.register_blueprint(deliveries_bp)
    app.register_blueprint(distribution_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auth_bp)

    # Захист всіх маршрутів за замовчуванням
    @app.before_request
    def require_login():
        public_endpoints = ['auth.login', 'static', 'changelog']
        if request.endpoint and not current_user.is_authenticated:
            if not any(endpoint == request.endpoint for endpoint in public_endpoints):
                return redirect(url_for('auth.login'))

    # Головна сторінка перенаправляє на список замовлень
    @app.route('/')
    def index():
        return redirect(url_for('orders.orders_list'))

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
