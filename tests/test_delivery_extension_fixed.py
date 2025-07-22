import pytest
from app import create_app
from app.extensions import db
from app.models import Order, Client, Delivery
from datetime import date, datetime
import json

class TestDeliveryExtension:
    """Тести для функціональності продовження підписки"""
    
    @pytest.fixture
    def app(self):
        """Створює тестове додаток"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        """Створює тестовий клієнт"""
        return app.test_client()

    @pytest.fixture
    def sample_data(self, app):
        """Створює тестові дані"""
        with app.app_context():
            # Створюємо тестового клієнта
            client = Client(instagram='test_user')
            db.session.add(client)
            db.session.flush()
            
            # Створюємо тестове замовлення підписки
            order = Order(
                client_id=client.id,
                recipient_name='Test User',
                recipient_phone='+380123456789',
                city='Київ',
                street='Test Street',
                delivery_type='Weekly',
                size='M',
                first_delivery_date=date.today(),
                delivery_day='ПН',
                for_whom='дівчина собі'
            )
            db.session.add(order)
            db.session.flush()
            
            # Створюємо доставки для цього замовлення
            # 4 оплачені доставки
            for i in range(4):
                delivery = Delivery(
                    order_id=order.id,
                    client_id=client.id,
                    delivery_date=date.today(),
                    status='Очікує',
                    is_subscription=True,
                    delivery_type='Weekly',
                    size='M',
                    phone='+380123456789'
                )
                db.session.add(delivery)
            
            # 1 не оплачена доставка
            unpaid_delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                delivery_date=date.today(),
                status='Не оплачена',
                is_subscription=False,
                delivery_type='Weekly',
                size='M',
                phone='+380123456789'
            )
            db.session.add(unpaid_delivery)
            
            db.session.commit()
            
            # Повертаємо ID замість об'єктів щоб уникнути DetachedInstanceError
            return {
                'client_id': client.id,
                'client_instagram': client.instagram,
                'order_id': order.id,
                'unpaid_delivery_id': unpaid_delivery.id
            }

    def test_extend_subscription_with_form_valid_data(self, client, sample_data):
        """Тест продовження підписки з валідними даними форми"""
        unpaid_delivery_id = sample_data['unpaid_delivery_id']
        client_instagram = sample_data['client_instagram']
        
        form_data = {
            'client_instagram': client_instagram,
            'recipient_name': 'Updated Name',
            'recipient_phone': '+380987654321',
            'city': 'Полтава',
            'street': 'Updated Street',
            'delivery_type': 'Monthly',
            'size': 'L',
            'delivery_day': 'ВТ',
            'for_whom': 'хлопець дівчині',
            'comment': 'Test comment',
            'preferences': 'Test preferences'
        }
        
        response = client.post(
            f'/deliveries/{unpaid_delivery_id}/extend-subscription-with-form',
            data=form_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True

    def test_extend_subscription_missing_required_fields(self, client, sample_data):
        """Тест продовження підписки з відсутніми обов'язковими полями"""
        unpaid_delivery_id = sample_data['unpaid_delivery_id']
        
        form_data = {
            'client_instagram': 'test_user',
            # Відсутні обов'язкові поля
        }
        
        response = client.post(
            f'/deliveries/{unpaid_delivery_id}/extend-subscription-with-form',
            data=form_data
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'обов\'язкові поля' in data['error']

    def test_extend_subscription_custom_size_with_amount(self, client, sample_data):
        """Тест продовження підписки з власним розміром та сумою"""
        unpaid_delivery_id = sample_data['unpaid_delivery_id']
        client_instagram = sample_data['client_instagram']
        
        form_data = {
            'client_instagram': client_instagram,
            'recipient_name': 'Test',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'Власний',
            'custom_amount': '500',
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        response = client.post(
            f'/deliveries/{unpaid_delivery_id}/extend-subscription-with-form',
            data=form_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True 