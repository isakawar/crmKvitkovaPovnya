from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from app.models.client import Client
from app.models.order import Order
# from app.models.price import Price  # Видалено
from app.models.delivery import Delivery
from app.models.courier import Courier
from .settings import Settings 