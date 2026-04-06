from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .client import Client
from .courier import Courier
from .subscription import Subscription
from .order import Order
from .delivery import Delivery
from .settings import Settings
from .user import User, Role
from .delivery_route import DeliveryRoute, RouteDelivery
from .price import Price
from .certificate import Certificate

__all__ = ['Client', 'Courier', 'Subscription', 'Order', 'Delivery', 'Settings', 'User', 'Role', 'DeliveryRoute', 'RouteDelivery', 'Price', 'Certificate']