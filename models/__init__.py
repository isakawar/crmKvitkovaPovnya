from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .client import Client
from .order import Order
from .price import Price
from .delivery import Delivery 