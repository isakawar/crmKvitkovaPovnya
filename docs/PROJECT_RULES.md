# Project Rules - Kvitkova CRM

## 📋 Загальні принципи

### 1. Архітектура та структура
- **Flask Application Factory Pattern** - використовуємо `create_app()` функцію
- **Blueprint Architecture** - кожен модуль у своєму blueprint
- **Service Layer** - бізнес-логіка в services/, не в routes/
- **Separation of Concerns** - розділення відповідальності між шарами

### 2. Код-стайл та якість
- **PEP 8** - стандарт Python коду
- **Type Hints** - обов'язково для всіх функцій
- **Docstrings** - документація для всіх публічних методів
- **Single Responsibility** - одна функція = одна відповідальність

### 3. Безпека
- **Input Validation** - валідація всіх вхідних даних
- **SQL Injection Protection** - використання параметризованих запитів
- **CSRF Protection** - включення Flask-WTF
- **Environment Variables** - секрети в .env файлі

---

## 🏗️ Архітектурні правила

### Структура проекту
```
app/
├── __init__.py          # Application Factory
├── config.py            # Конфігурація
├── extensions.py        # Flask extensions
├── blueprints/          # Модулі додатку
│   ├── orders/
│   ├── clients/
│   ├── deliveries/
│   └── settings/
├── models/              # SQLAlchemy моделі
├── services/            # Бізнес-логіка
├── utils/               # Допоміжні функції
├── templates/           # Jinja2 шаблони
└── static/              # Статичні файли
```

### Правила для Blueprints
```python
# ✅ Правильно
from flask import Blueprint, render_template, request, jsonify
from app.services.order_service import OrderService
from app.utils.validators import validate_order_data

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    """Список замовлень з фільтрацією"""
    filters = request.args
    orders = OrderService.get_filtered_orders(filters)
    return render_template('orders_list.html', orders=orders)

# ❌ Неправильно
@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    # Бізнес-логіка прямо в route
    query = Order.query
    if request.args.get('phone'):
        query = query.filter(Order.phone.contains(request.args['phone']))
    # ... багато коду
```

### Правила для Services
```python
# ✅ Правильно
class OrderService:
    @staticmethod
    def create_order(data: dict) -> Order:
        """Створює замовлення з валідацією"""
        validate_order_data(data)
        order = Order(**data)
        db.session.add(order)
        db.session.commit()
        return order

    @staticmethod
    def get_filtered_orders(filters: dict) -> List[Order]:
        """Отримує замовлення з фільтрами"""
        query = Order.query
        if filters.get('city'):
            query = query.filter(Order.city == filters['city'])
        return query.all()

# ❌ Неправильно
def create_order(form_data):
    # Без валідації, без типізації
    order = Order()
    order.name = form_data['name']
    # ... без обробки помилок
```

---

## 🔧 Код-стайл та якість

### Типізація
```python
# ✅ Обов'язково
from typing import List, Optional, Dict, Any
from datetime import date

def create_order(
    client_id: int,
    recipient_name: str,
    delivery_date: date,
    status: str = "pending"
) -> Order:
    """Створює нове замовлення"""
    pass

# ❌ Неправильно
def create_order(client_id, recipient_name, delivery_date, status="pending"):
    pass
```

### Валідація даних
```python
# ✅ Правильно
from marshmallow import Schema, fields, ValidationError

class OrderSchema(Schema):
    client_id = fields.Integer(required=True)
    recipient_name = fields.Str(required=True, validate=Length(min=2, max=100))
    delivery_date = fields.Date(required=True)

def validate_order_data(data: dict) -> dict:
    """Валідує дані замовлення"""
    schema = OrderSchema()
    try:
        return schema.load(data)
    except ValidationError as e:
        raise ValueError(f"Invalid order data: {e.messages}")

# ❌ Неправильно
def create_order(data):
    # Без валідації
    order = Order(**data)
```

### Обробка помилок
```python
# ✅ Правильно
from flask import jsonify
from sqlalchemy.exc import IntegrityError

@orders_bp.route('/orders', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        validated_data = validate_order_data(data)
        order = OrderService.create_order(validated_data)
        return jsonify({'success': True, 'order_id': order.id}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except IntegrityError:
        return jsonify({'error': 'Order already exists'}), 409
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ❌ Неправильно
@orders_bp.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    order = Order(**data)  # Без обробки помилок
    db.session.add(order)
    db.session.commit()
    return jsonify({'success': True})
```

---

## 🛡️ Безпека

### Валідація вхідних даних
```python
# ✅ Правильно
import re
from werkzeug.security import safe_str_cmp

def validate_phone(phone: str) -> bool:
    """Валідує український номер телефону"""
    pattern = r'^\+380[0-9]{9}$'
    return bool(re.match(pattern, phone))

def validate_instagram(instagram: str) -> bool:
    """Валідує Instagram username"""
    pattern = r'^[a-zA-Z0-9._]{1,30}$'
    return bool(re.match(pattern, instagram))

# ❌ Неправильно
def create_order(data):
    # Без валідації
    order = Order(**data)
```

### SQL Injection Protection
```python
# ✅ Правильно - використовуємо SQLAlchemy ORM
orders = Order.query.filter(Order.city == city).all()

# ✅ Правильно - параметризовані запити
query = text("SELECT * FROM orders WHERE city = :city")
result = db.session.execute(query, {'city': city})

# ❌ Неправильно - SQL injection
query = f"SELECT * FROM orders WHERE city = '{city}'"
```

### CSRF Protection
```python
# ✅ Правильно
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    csrf.init_app(app)
    return app

# В шаблонах
<form method="POST">
    {{ csrf_token() }}
    <!-- form fields -->
</form>
```

---

## 🧪 Тестування

### Структура тестів
```
tests/
├── __init__.py
├── conftest.py          # Fixtures
├── test_models/         # Тести моделей
├── test_services/       # Тести сервісів
├── test_views/          # Тести views
└── test_integration/    # Інтеграційні тести
```

### Приклади тестів
```python
# ✅ Правильно
import pytest
from app.models import Order
from app.services.order_service import OrderService

class TestOrderService:
    def test_create_order_success(self, db_session):
        """Тест успішного створення замовлення"""
        data = {
            'client_id': 1,
            'recipient_name': 'Test User',
            'delivery_date': date(2024, 1, 1)
        }
        order = OrderService.create_order(data)
        assert order.id is not None
        assert order.recipient_name == 'Test User'

    def test_create_order_invalid_data(self, db_session):
        """Тест валідації некоректних даних"""
        data = {'client_id': 'invalid'}
        with pytest.raises(ValueError):
            OrderService.create_order(data)

# ❌ Неправильно
def test_order():
    # Без fixtures, без очищення БД
    order = Order(name="test")
    assert order.name == "test"
```

---

## 📊 Логування

### Налаштування логування
```python
# ✅ Правильно
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """Налаштовує логування для додатку"""
    if not app.debug:
        file_handler = RotatingFileHandler(
            'logs/app.log', 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')

# Використання
logger = logging.getLogger(__name__)

def create_order(data):
    logger.info(f"Creating order for client {data['client_id']}")
    try:
        order = Order(**data)
        db.session.add(order)
        db.session.commit()
        logger.info(f"Order {order.id} created successfully")
        return order
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise
```

---

## 🔄 Рекомендації для рефакторингу

### 1. Моделі даних
**Поточні проблеми:**
- Денормалізовані поля в Order (`bouquet_size`, `price_at_order`)
- Відсутність індексів для швидкого пошуку
- Немає soft delete для важливих записів

**Рекомендації:**
```python
# ✅ Після рефакторингу
class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='active', index=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    # Relationships
    client = db.relationship('Client', backref='orders')
    deliveries = db.relationship('Delivery', backref='order', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        db.Index('idx_orders_client_status', 'client_id', 'status'),
        db.Index('idx_orders_created_at', 'created_at'),
    )
```

### 2. Сервіси та бізнес-логіка
**Поточні проблеми:**
- Бізнес-логіка розкидана по routes
- Відсутність абстракцій для складних операцій
- Немає транзакцій для атомарних операцій

**Рекомендації:**
```python
# ✅ Після рефакторингу
from abc import ABC, abstractmethod
from typing import Protocol

class OrderRepository(Protocol):
    def create(self, data: dict) -> Order: ...
    def get_by_id(self, order_id: int) -> Optional[Order]: ...
    def update(self, order: Order, data: dict) -> Order: ...
    def delete(self, order_id: int) -> None: ...

class OrderService:
    def __init__(self, repository: OrderRepository):
        self.repository = repository
    
    def create_order_with_deliveries(self, data: dict) -> Order:
        """Створює замовлення з доставками в транзакції"""
        with db.session.begin():
            order = self.repository.create(data)
            deliveries = self._create_deliveries_for_order(order)
            return order
    
    def _create_deliveries_for_order(self, order: Order) -> List[Delivery]:
        """Створює доставки для замовлення"""
        # Логіка створення доставок
        pass
```

### 3. API та валідація
**Поточні проблеми:**
- Валідація в шаблонах
- Відсутність API схем
- Немає версіонування API

**Рекомендації:**
```python
# ✅ Після рефакторингу
from marshmallow import Schema, fields

class OrderSchema(Schema):
    id = fields.Int(dump_only=True)
    client_id = fields.Int(required=True)
    recipient_name = fields.Str(required=True, validate=Length(min=2, max=100))
    delivery_date = fields.Date(required=True)
    
    class Meta:
        unknown = EXCLUDE

@orders_bp.route('/api/v1/orders', methods=['POST'])
def create_order_api():
    """API endpoint для створення замовлення"""
    schema = OrderSchema()
    try:
        data = schema.load(request.get_json())
        order = OrderService.create_order(data)
        return schema.dump(order), 201
    except ValidationError as e:
        return {'errors': e.messages}, 400
```

### 4. Конфігурація та середовища
**Поточні проблеми:**
- Хардкод конфігурації
- Відсутність .env файлів
- Немає різних конфігурацій для середовищ

**Рекомендації:**
```python
# ✅ Після рефакторингу
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    
    # Security
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
```

### 5. Тестування та якість коду
**Поточні проблеми:**
- Відсутність тестів
- Немає linting та formatting
- Відсутність CI/CD

**Рекомендації:**
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install black flake8 mypy pytest
    - name: Lint with flake8
      run: flake8 app tests
    - name: Format check with black
      run: black --check app tests
    - name: Type check with mypy
      run: mypy app
    - name: Test with pytest
      run: pytest
```

---

## 📝 Чек-лист для нових функцій

### Перед додаванням нової функції:
- [ ] Чи потрібна валідація вхідних даних?
- [ ] Чи потрібна обробка помилок?
- [ ] Чи потрібні тести?
- [ ] Чи потрібне логування?
- [ ] Чи потрібна документація?
- [ ] Чи не порушує принципи SOLID?
- [ ] Чи не дублює існуючий код?

### При додаванні нових моделей:
- [ ] Чи є індекси для швидкого пошуку?
- [ ] Чи є валідація на рівні моделі?
- [ ] Чи є relationships правильно налаштовані?
- [ ] Чи є cascade delete налаштований?

### При додаванні нових API endpoints:
- [ ] Чи є валідація вхідних даних?
- [ ] Чи є правильні HTTP статуси?
- [ ] Чи є обробка помилок?
- [ ] Чи є документація API?

---

## 🚀 Наступні кроки для рефакторингу

### Пріоритет 1 (Критично):
1. **Додати валідацію даних** - використовувати Marshmallow
2. **Розділити бізнес-логіку** - винести з routes в services
3. **Додати тести** - покрити критичну функціональність
4. **Налаштувати логування** - для відстеження помилок

### Пріоритет 2 (Важливо):
1. **Рефакторинг моделей** - додати індекси, валідацію
2. **API версіонування** - для майбутнього розвитку
3. **Кешування** - для швидких запитів
4. **Моніторинг** - для відстеження продуктивності

### Пріоритет 3 (Бажано):
1. **CI/CD pipeline** - автоматизація тестування
2. **Документація API** - Swagger/OpenAPI
3. **Мікросервісна архітектура** - для масштабування
4. **Контейнеризація** - Docker для розгортання

---

## 📚 Корисні ресурси

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Marshmallow Documentation](https://marshmallow.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Flask Security Best Practices](https://flask-security.readthedocs.io/)

---

*Цей документ є живим і повинен оновлюватися разом з розвитком проекту.* 