import pytest
from app.services.order_service import get_or_create_client, create_order_and_deliveries
from datetime import date
import datetime

class TestOrderService:
    def test_get_or_create_client_existing(self, db_session, sample_client):
        """Тест отримання існуючого клієнта"""
        client, error = get_or_create_client(sample_client.instagram)
        
        assert client is not None
        assert error is None
        assert client.id == sample_client.id
    
    def test_get_or_create_client_nonexistent(self, db_session):
        """Тест з неіснуючим клієнтом"""
        client, error = get_or_create_client('nonexistent_user')
        
        assert client is None
        assert error is not None
        assert 'не знайдений' in error
    
    def test_create_order_and_deliveries_success(self, db_session, sample_client):
        """Тест успішного створення замовлення та доставок"""
        form_data = {
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'Weekly',
            'size': 'M',
            'first_delivery_date': (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        order = create_order_and_deliveries(sample_client, form_data)
        
        assert order.id is not None
        assert order.recipient_name == 'Test User'
        assert order.client_id == sample_client.id
        
        # Перевіряємо, що створилися доставки
        from app.models import Delivery
        deliveries = Delivery.query.filter_by(order_id=order.id).all()
        assert len(deliveries) >= 1
    
    def test_create_order_with_custom_amount(self, db_session, sample_client):
        """Тест створення замовлення з власним розміром та сумою"""
        form_data = {
            'recipient_name': 'Test User',
            'recipient_phone': '+380123456789',
            'city': 'Київ',
            'street': 'Test Street',
            'delivery_type': 'One-time',
            'size': 'Власний',
            'custom_amount': '500',
            'first_delivery_date': (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
            'delivery_day': 'ПН',
            'for_whom': 'дівчина собі'
        }
        
        order = create_order_and_deliveries(sample_client, form_data)
        
        assert order.id is not None
        assert order.size == 'Власний'
        assert order.custom_amount == 500 