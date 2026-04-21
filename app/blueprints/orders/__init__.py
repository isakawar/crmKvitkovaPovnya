from flask import Blueprint

orders_bp = Blueprint('orders', __name__)

from app.blueprints.orders import orders  # noqa: E402, F401
from app.blueprints.orders import deliveries  # noqa: E402, F401
from app.blueprints.orders import route_generator  # noqa: E402, F401
from app.blueprints.orders import route_saver  # noqa: E402, F401
from app.blueprints.orders import route_distribute  # noqa: E402, F401
