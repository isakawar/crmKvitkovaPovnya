from flask import Blueprint

subscriptions_bp = Blueprint('subscriptions', __name__)

from app.blueprints.subscriptions import routes  # noqa
