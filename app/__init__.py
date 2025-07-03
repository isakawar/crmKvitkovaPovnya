import os
from flask import Flask, render_template
from app.extensions import db, migrate
from app.config import config_map
from app.blueprints.orders.routes import orders_bp
from app.blueprints.clients.routes import clients_bp
from app.blueprints.deliveries.routes import deliveries_bp
from app.blueprints.prices.routes import prices_bp
from app.blueprints.reports.routes import reports_bp

def create_app(config_name=None):
    app = Flask(__name__)
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'development')
    app.config.from_object(config_map[config_name])
    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(orders_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(deliveries_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(reports_bp)
    @app.route('/')
    def index():
        return render_template('index.html')
    return app
