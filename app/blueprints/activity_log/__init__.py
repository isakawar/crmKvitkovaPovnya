from flask import Blueprint

activity_log_bp = Blueprint('activity_log', __name__)

from app.blueprints.activity_log import routes  # noqa: F401, E402
