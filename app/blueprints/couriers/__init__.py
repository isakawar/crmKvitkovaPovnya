from flask import Blueprint

couriers_bp = Blueprint('couriers', __name__)

from . import routes 