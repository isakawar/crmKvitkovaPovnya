from flask import Blueprint

certificates_bp = Blueprint('certificates', __name__)

from app.blueprints.certificates import routes  # noqa
