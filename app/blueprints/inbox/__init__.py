from flask import Blueprint

inbox_bp = Blueprint('inbox', __name__)

from app.blueprints.inbox import routes  # noqa: F401, E402
