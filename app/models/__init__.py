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
from .price_preset import PricePreset
from .price import Price
from .certificate import Certificate
from .order_photo import OrderPhoto
from .route_dispatch_log import RouteDispatchLog
from .expense_category import ExpenseCategory

__all__ = ['Client', 'Courier', 'Subscription', 'Order', 'Delivery', 'Settings', 'User', 'Role', 'DeliveryRoute', 'RouteDelivery', 'PricePreset', 'Price', 'Certificate', 'OrderPhoto', 'RouteDispatchLog', 'ExpenseCategory']