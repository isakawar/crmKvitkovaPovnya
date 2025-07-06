import os
from flask import Flask, render_template, send_file, Response
from app.extensions import db, migrate
from app.config import config_map
from app.blueprints.orders.routes import orders_bp
from app.blueprints.clients.routes import clients_bp
from app.blueprints.deliveries.routes import deliveries_bp
# from app.blueprints.prices.routes import prices_bp
from app.blueprints.reports.routes import reports_bp
from app.blueprints.settings.routes import settings_bp

def get_version():
    try:
        with open(os.path.join(os.path.dirname(__file__), '..', 'VERSION')) as f:
            return f.read().strip()
    except Exception:
        return 'dev'

def create_app(config_name=None):
    app = Flask(__name__)
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'development')
    app.config.from_object(config_map[config_name])
    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(orders_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(deliveries_bp)
    # app.register_blueprint(prices_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    version = get_version()
    @app.context_processor
    def inject_version():
        return dict(app_version=version)
    @app.route('/')
    def index():
        return render_template('index.html')
    @app.route('/changelog')
    def changelog():
        try:
            with open('CHANGELOG.md', encoding='utf-8') as f:
                content = f.read()
            return Response(content, mimetype='text/plain')
        except Exception as e:
            return Response('Changelog недоступний', mimetype='text/plain', status=404)
    return app
