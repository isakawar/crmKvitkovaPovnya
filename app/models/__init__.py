from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .client import Client
from .courier import Courier
from .delivery import Delivery
from .order import Order
from .settings import Settings
from .user import User, Role

__all__ = ['Client', 'Courier', 'Delivery', 'Order', 'Settings', 'User', 'Role'] 