import pytest
from app import create_app
from app.extensions import db
from app.models import Order, Client, Delivery
from app.models.settings import Settings
from datetime import date, datetime, timedelta
import json

class TestOrders:
    """Тести для функціональності замовлень"""
    
    @pytest.fixture
    def app(self):
        """Створює тестове додаток"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            db.create_all()
            
            # Створюємо базові налаштування
            settings_data = [
                ('city', 'Київ'),
                ('city', 'Полтава'),
                ('delivery_type', 'Weekly'),
                ('delivery_type', 'Monthly'),
                ('delivery_type', 'One-time'),
                ('size', 'M'),
                ('size', 'L'),
                ('size', 'Власний'),
                ('for_whom', 'дівчина собі'),
                ('for_whom', 'хлопець дівчині'),
            ]
            
            for setting_type, value in settings_data:
                setting = Settings(type=setting_type, value=value)
                db.session.add(setting)
            
            # Створюємо тестового клієнта
            client = Client(instagram='test_user')
            db.session.add(client)
            
            db.session.commit()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        """Створює тестовий клієнт"""
        return app.test_client()

    def test_create_order_basic(self, client, app):
        """Тест створення базового замовлення"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        form_data = {
            'client_instagram': 'test_user',
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'M',
            'first_delivery_date': tomorrow,
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Якщо це AJAX запит, очікуємо JSON
        if response.headers.get('Content-Type') == 'application/json':
            data = json.loads(response.data)
            assert data['success'] == True
        else:
            # Якщо це звичайний POST, очікуємо редирект
            assert response.status_code in [200, 302]

    def test_create_order_custom_size_with_amount(self, client, app):
        """Тест створення замовлення з власним розміром та сумою"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        form_data = {
            'client_instagram': 'test_user',
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'Власний',
            'custom_amount': '500',
            'first_delivery_date': tomorrow,
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Якщо це AJAX запит, очікуємо JSON
        if response.headers.get('Content-Type') == 'application/json':
            data = json.loads(response.data)
            assert data['success'] == True
        else:
            # Якщо це звичайний POST, очікуємо редирект
            assert response.status_code in [200, 302]

    def test_create_order_custom_size_without_amount(self, client, app):
        """Тест створення замовлення з власним розміром але без суми (має бути помилка)"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        form_data = {
            'client_instagram': 'test_user',
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'Власний',
            # custom_amount відсутній
            'first_delivery_date': tomorrow,
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Очікуємо помилку
        assert response.status_code == 400

    def test_create_order_missing_required_fields(self, client, app):
        """Тест створення замовлення з відсутніми обов'язковими полями"""
        form_data = {
            'client_instagram': 'test_user',
            # Відсутні обов'язкові поля
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Очікуємо помилку
        assert response.status_code == 400

    def test_create_order_pickup(self, client, app):
        """Тест створення замовлення самовивозом"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        form_data = {
            'client_instagram': 'test_user',
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'is_pickup': 'on',  # Самовивіз
            'delivery_type': 'One-time',
            'size': 'L',
            'first_delivery_date': tomorrow,
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Для самовивозу адреса не потрібна
        if response.headers.get('Content-Type') == 'application/json':
            data = json.loads(response.data)
            assert data['success'] == True
        else:
            assert response.status_code in [200, 302]

    def test_create_order_invalid_phone(self, client, app):
        """Тест створення замовлення з неправильним номером телефону"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        form_data = {
            'client_instagram': 'test_user',
            'recipient_name': 'Test User',
            'recipient_phone': 'invalid_phone',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'M',
            'first_delivery_date': tomorrow,
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Очікуємо помилку через неправильний номер
        assert response.status_code == 400

    def test_create_order_nonexistent_client(self, client, app):
        """Тест створення замовлення з неіснуючим клієнтом"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        form_data = {
            'client_instagram': 'nonexistent_user',
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'M',
            'first_delivery_date': tomorrow,
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post('/orders/new', data=form_data)
        
        # Очікуємо помилку через неіснуючого клієнта
        assert response.status_code == 400 