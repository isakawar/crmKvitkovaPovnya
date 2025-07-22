# План рефакторингу - Kvitkova CRM

## 🔍 Аналіз поточного стану

### Позитивні аспекти:
- ✅ Хороша структура з blueprints
- ✅ Використання SQLAlchemy ORM
- ✅ Розділення на services та models
- ✅ Flask Application Factory pattern

### Проблеми, що потребують вирішення:

---

## 🚨 Пріоритет 1: Критичні проблеми

### 1. Відсутність валідації даних ✅ ВИКОНАНО

**Поточний код (проблемний):**
```python
# app/blueprints/orders/routes.py
@orders_bp.route('/orders/new', methods=['POST'])
def order_create():
    # Без валідації!
    order = Order(
        client_id=client.id,
        recipient_name=request.form['recipient_name'],
        recipient_phone=request.form['recipient_phone'],
        # ... без перевірки даних
    )
```

**Рішення - додати Marshmallow схеми:**
```python
# app/schemas/order_schema.py
from marshmallow import Schema, fields, ValidationError, validates
import re

class OrderSchema(Schema):
    client_instagram = fields.Str(required=True, validate=Length(min=1, max=100))
    recipient_name = fields.Str(required=True, validate=Length(min=2, max=100))
    recipient_phone = fields.Str(required=True)
    city = fields.Str(required=True, validate=Length(min=1, max=64))
    delivery_type = fields.Str(required=True, validate=OneOf(['Weekly', 'Monthly', 'Bi-weekly', 'One-time']))
    size = fields.Str(required=True, validate=OneOf(['M', 'L', 'XL', 'XXL', 'Власний']))
    first_delivery_date = fields.Date(required=True)
    delivery_day = fields.Str(required=True, validate=OneOf(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'НД']))
    for_whom = fields.Str(required=True, validate=Length(min=1, max=64))
    
    @validates('recipient_phone')
    def validate_phone(self, value):
        pattern = r'^\+380[0-9]{9}$'
        if not re.match(pattern, value):
            raise ValidationError('Телефон має бути у форматі +380XXXXXXXXX')
        return value
    
    @validates('client_instagram')
    def validate_instagram(self, value):
        pattern = r'^[a-zA-Z0-9._]{1,30}$'
        if not re.match(pattern, value):
            raise ValidationError('Некорректний Instagram username')
        return value

# Використання в routes
@orders_bp.route('/orders/new', methods=['POST'])
def order_create():
    schema = OrderSchema()
    try:
        validated_data = schema.load(request.form)
        order = OrderService.create_order(validated_data)
        return jsonify({'success': True, 'order_id': order.id}), 201
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400
```

### 2. Бізнес-логіка в routes

**Поточний код (проблемний):**
```python
# app/blueprints/orders/routes.py - 331 рядків!
@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    # 50+ рядків бізнес-логіки прямо в route
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    # ... багато коду фільтрації
```

**Рішення - винести в services:**
```python
# app/services/order_service.py
class OrderService:
    @staticmethod
    def get_filtered_orders(filters: dict) -> List[Order]:
        """Отримує замовлення з фільтрами"""
        query = Order.query.join(Client)
        
        if filters.get('phone'):
            query = query.filter(Order.recipient_phone.contains(filters['phone']))
        if filters.get('instagram'):
            query = query.filter(Client.instagram.contains(filters['instagram']))
        if filters.get('city'):
            query = query.filter(Order.city == filters['city'])
        if filters.get('delivery_type'):
            query = query.filter(Order.delivery_type == filters['delivery_type'])
        if filters.get('size'):
            query = query.filter(Order.size == filters['size'])
            
        return query.order_by(Order.id.desc()).all()
    
    @staticmethod
    def get_orders_stats() -> dict:
        """Отримує статистику замовлень"""
        return {
            'total_orders': Order.query.count(),
            'clients_count': db.session.query(Order.client_id).distinct().count(),
            'subscription_extensions': Order.query.filter_by(is_subscription_extended=True).count()
        }

# Спрощений route
@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    """Список замовлень з фільтрацією"""
    filters = request.args.to_dict()
    orders = OrderService.get_filtered_orders(filters)
    stats = OrderService.get_orders_stats()
    
    return render_template('orders_list.html', 
                         orders=orders, 
                         stats=stats)
```

### 3. Відсутність обробки помилок ✅ ВИКОНАНО

**Поточний код (проблемний):**
```python
@orders_bp.route('/orders/<int:order_id>/edit', methods=['POST'])
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)
    # Без try-catch!
    update_order(order, request.form)
    return jsonify({'success': True})
```

**Рішення:**
```python
@orders_bp.route('/orders/<int:order_id>/edit', methods=['POST'])
def order_edit(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        schema = OrderSchema()
        validated_data = schema.load(request.form)
        
        OrderService.update_order(order, validated_data)
        return jsonify({'success': True, 'message': 'Замовлення оновлено'})
        
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating order {order_id}: {e}")
        return jsonify({'error': 'Внутрішня помилка сервера'}), 500
```

---

## 🔧 Пріоритет 2: Архітектурні покращення

### 1. Рефакторинг моделей

**Поточні проблеми в моделях:**
```python
# app/models/order.py
class Order(db.Model):
    # Денормалізовані поля
    bouquet_size = db.Column(db.String(16))
    price_at_order = db.Column(db.Integer)
    periodicity = db.Column(db.String(8))
    preferred_days = db.Column(db.String(64))
    
    # Відсутність індексів
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    # Немає updated_at
```

**Покращений код:**
```python
# app/models/order.py
class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    
    # Основні поля
    recipient_name = db.Column(db.String(128), nullable=False)
    recipient_phone = db.Column(db.String(32), nullable=False, index=True)
    recipient_social = db.Column(db.String(128))
    
    # Адреса
    city = db.Column(db.String(64), nullable=False, index=True)
    street = db.Column(db.String(128), nullable=False)
    building_number = db.Column(db.String(32))
    floor = db.Column(db.String(16))
    entrance = db.Column(db.String(16))
    is_pickup = db.Column(db.Boolean, default=False)
    
    # Доставка
    delivery_type = db.Column(db.String(32), nullable=False, index=True)
    size = db.Column(db.String(32), nullable=False)
    custom_amount = db.Column(db.Integer)
    
    # Дати
    first_delivery_date = db.Column(db.Date, nullable=False, index=True)
    delivery_day = db.Column(db.String(16), nullable=False)
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))
    
    # Додаткова інформація
    comment = db.Column(db.Text)
    preferences = db.Column(db.Text)
    for_whom = db.Column(db.String(64), nullable=False)
    
    # Системні поля
    created_at = db.Column(db.DateTime, default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Relationships
    client = db.relationship('Client', backref='orders')
    deliveries = db.relationship('Delivery', backref='order', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        db.Index('idx_orders_client_status', 'client_id', 'is_active'),
        db.Index('idx_orders_city_type', 'city', 'delivery_type'),
        db.Index('idx_orders_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f'<Order {self.id}: {self.recipient_name}>'
```

### 2. Додати Repository Pattern

```python
# app/repositories/order_repository.py
from typing import List, Optional, Dict, Any
from app.models import Order, Client
from app.extensions import db

class OrderRepository:
    @staticmethod
    def create(data: dict) -> Order:
        """Створює нове замовлення"""
        order = Order(**data)
        db.session.add(order)
        db.session.commit()
        return order
    
    @staticmethod
    def get_by_id(order_id: int) -> Optional[Order]:
        """Отримує замовлення за ID"""
        return Order.query.get(order_id)
    
    @staticmethod
    def get_filtered(filters: dict) -> List[Order]:
        """Отримує замовлення з фільтрами"""
        query = Order.query.join(Client)
        
        if filters.get('phone'):
            query = query.filter(Order.recipient_phone.contains(filters['phone']))
        if filters.get('instagram'):
            query = query.filter(Client.instagram.contains(filters['instagram']))
        if filters.get('city'):
            query = query.filter(Order.city == filters['city'])
        if filters.get('delivery_type'):
            query = query.filter(Order.delivery_type == filters['delivery_type'])
        if filters.get('size'):
            query = query.filter(Order.size == filters['size'])
            
        return query.order_by(Order.id.desc()).all()
    
    @staticmethod
    def update(order: Order, data: dict) -> Order:
        """Оновлює замовлення"""
        for key, value in data.items():
            setattr(order, key, value)
        db.session.commit()
        return order
    
    @staticmethod
    def delete(order_id: int) -> bool:
        """Видаляє замовлення (soft delete)"""
        order = Order.query.get(order_id)
        if order:
            order.is_active = False
            db.session.commit()
            return True
        return False
```

### 3. Покращити Services ✅ ВИКОНАНО

```python
# app/services/order_service.py
from typing import List, Optional, Dict, Any
from app.repositories.order_repository import OrderRepository
from app.schemas.order_schema import OrderSchema
from app.models import Order, Client, Delivery
import logging

logger = logging.getLogger(__name__)

class OrderService:
    def __init__(self, repository: OrderRepository):
        self.repository = repository
        self.schema = OrderSchema()
    
    def create_order(self, data: dict) -> Order:
        """Створює замовлення з валідацією"""
        try:
            # Валідація даних
            validated_data = self.schema.load(data)
            
            # Отримання клієнта
            client = self._get_or_create_client(validated_data['client_instagram'])
            validated_data['client_id'] = client.id
            
            # Створення замовлення
            order = self.repository.create(validated_data)
            
            # Створення доставок
            self._create_deliveries_for_order(order)
            
            logger.info(f"Order {order.id} created successfully")
            return order
            
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise
    
    def get_orders_with_filters(self, filters: dict) -> List[Order]:
        """Отримує замовлення з фільтрами"""
        return self.repository.get_filtered(filters)
    
    def update_order(self, order_id: int, data: dict) -> Order:
        """Оновлює замовлення"""
        try:
            order = self.repository.get_by_id(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            validated_data = self.schema.load(data, partial=True)
            return self.repository.update(order, validated_data)
            
        except Exception as e:
            logger.error(f"Failed to update order {order_id}: {e}")
            raise
    
    def _get_or_create_client(self, instagram: str) -> Client:
        """Отримує або створює клієнта"""
        client = Client.query.filter_by(instagram=instagram).first()
        if not client:
            raise ValueError(f"Client with Instagram {instagram} not found")
        return client
    
    def _create_deliveries_for_order(self, order: Order) -> List[Delivery]:
        """Створює доставки для замовлення"""
        # Логіка створення доставок (існуюча)
        pass
```

---

## 🛡️ Пріоритет 3: Безпека та конфігурація

### 1. Налаштування конфігурації ✅ ВИКОНАНО

```python
# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    
    # Pagination
    ORDERS_PER_PAGE = int(os.environ.get('ORDERS_PER_PAGE', '30'))
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}
```

### 2. Додати логування ✅ ВИКОНАНО

```python
# app/utils/logger.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(app):
    """Налаштовує логування для додатку"""
    if not app.debug and not app.testing:
        # Створюємо папку для логів
        os.makedirs('logs', exist_ok=True)
        
        # File handler
        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s'
        ))
        app.logger.addHandler(console_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')

# Використання в __init__.py
def create_app(config_name=None):
    app = Flask(__name__)
    # ... інші налаштування
    setup_logging(app)
    return app
```

### 3. Додати CSRF захист

```python
# app/extensions.py
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

# В __init__.py
def create_app(config_name=None):
    app = Flask(__name__)
    # ... інші налаштування
    csrf.init_app(app)
    return app

# В шаблонах
<form method="POST">
    {{ csrf_token() }}
    <!-- form fields -->
</form>
```

---

## 🧪 Пріоритет 4: Тестування

### 1. Базова структура тестів

```python
# tests/conftest.py
import pytest
from app import create_app
from app.extensions import db
from app.models import Order, Client, Delivery

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session

@pytest.fixture
def sample_client(db_session):
    client = Client(instagram='test_user')
    db_session.add(client)
    db_session.commit()
    return client

@pytest.fixture
def sample_order(db_session, sample_client):
    order = Order(
        client_id=sample_client.id,
        recipient_name='Test User',
        recipient_phone='+380123456789',
        city='Київ',
        street='Test Street',
        delivery_type='Weekly',
        size='M',
        first_delivery_date=date(2024, 1, 1),
        delivery_day='ПН',
        for_whom='Для себе'
    )
    db_session.add(order)
    db_session.commit()
    return order
```

### 2. Тести для Services

```python
# tests/test_services/test_order_service.py
import pytest
from app.services.order_service import OrderService
from app.repositories.order_repository import OrderRepository
from app.schemas.order_schema import OrderSchema

class TestOrderService:
    def test_create_order_success(self, db_session, sample_client):
        """Тест успішного створення замовлення"""
        repository = OrderRepository()
        service = OrderService(repository)
        
        data = {
            'client_instagram': sample_client.instagram,
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'M',
            'first_delivery_date': '2024-01-01',
            'delivery_day': 'ПН',
            'for_whom': 'Для себе'
        }
        
        order = service.create_order(data)
        assert order.id is not None
        assert order.recipient_name == 'Test User'
        assert order.client_id == sample_client.id
    
    def test_create_order_invalid_data(self, db_session):
        """Тест валідації некоректних даних"""
        repository = OrderRepository()
        service = OrderService(repository)
        
        data = {
            'client_instagram': 'invalid_instagram!',
            'recipient_phone': 'invalid_phone'
        }
        
        with pytest.raises(ValueError):
            service.create_order(data)
```

### 3. Тести для Views

```python
# tests/test_views/test_orders.py
import pytest
from flask import url_for

class TestOrdersViews:
    def test_orders_list_page(self, client):
        """Тест сторінки списку замовлень"""
        response = client.get('/orders')
        assert response.status_code == 200
        assert b'orders_list.html' in response.data
    
    def test_create_order_success(self, client, sample_client):
        """Тест створення замовлення"""
        data = {
            'client_instagram': sample_client.instagram,
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'M',
            'first_delivery_date': '2024-01-01',
            'delivery_day': 'ПН',
            'for_whom': 'Для себе'
        }
        
        response = client.post('/orders/new', data=data)
        assert response.status_code == 302  # Redirect after success
    
    def test_create_order_invalid_data(self, client):
        """Тест створення замовлення з некоректними даними"""
        data = {
            'recipient_name': '',  # Empty required field
            'recipient_phone': 'invalid'
        }
        
        response = client.post('/orders/new', data=data)
        assert response.status_code == 400
```

---

## 📋 Чек-лист рефакторингу

### Етап 1: Критичні зміни
- [x] Додати Marshmallow схеми для валідації
- [x] Винести бізнес-логіку з routes в services
- [x] Додати обробку помилок у всіх endpoints
- [x] Налаштувати логування
- [ ] Додати CSRF захист

### Етап 2: Архітектурні покращення
- [ ] Рефакторинг моделей (індекси, валідація)
- [x] Додати Repository pattern
- [x] Покращити Services з dependency injection
- [x] Налаштувати конфігурацію для різних середовищ

### Етап 3: Тестування
- [x] Створити базову структуру тестів
- [x] Написати тести для Services
- [ ] Написати тести для Views
- [ ] Налаштувати CI/CD

### Етап 4: Оптимізація
- [ ] Додати кешування для швидких запитів
- [ ] Оптимізувати SQL запити
- [ ] Додати пагінацію для великих списків
- [ ] Налаштувати моніторинг

---

## 🚀 Команди для рефакторингу

```bash
# 1. Встановити додаткові залежності
pip install marshmallow python-dotenv pytest pytest-flask

# 2. Створити .env файл
echo "SECRET_KEY=your-secret-key-here" > .env
echo "DATABASE_URL=sqlite:///dev.db" >> .env
echo "LOG_LEVEL=INFO" >> .env

# 3. Запустити тести
pytest tests/

# 4. Перевірити код
flake8 app/
black app/
mypy app/
```

---

*Цей план рефакторингу заснований на аналізі поточного коду та найкращих практиках Flask розробки.* 