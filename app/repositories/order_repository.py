from typing import List, Optional, Dict, Any
from app.models import Order, Client
from app.extensions import db
import logging

logger = logging.getLogger(__name__)

class OrderRepository:
    """Repository для роботи з замовленнями"""
    
    @staticmethod
    def create(data: dict) -> Order:
        """Створює нове замовлення"""
        try:
            order = Order(**data)
            db.session.add(order)
            db.session.commit()
            logger.info(f"Order {order.id} created successfully")
            return order
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create order: {e}")
            raise
    
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
        try:
            for key, value in data.items():
                if hasattr(order, key):
                    setattr(order, key, value)
            db.session.commit()
            logger.info(f"Order {order.id} updated successfully")
            return order
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update order {order.id}: {e}")
            raise
    
    @staticmethod
    def delete(order_id: int) -> bool:
        """Видаляє замовлення (soft delete)"""
        try:
            order = Order.query.get(order_id)
            if order:
                order.is_active = False
                db.session.commit()
                logger.info(f"Order {order_id} deleted successfully")
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete order {order_id}: {e}")
            raise
    
    @staticmethod
    def get_stats() -> dict:
        """Отримує статистику замовлень"""
        return {
            'total_orders': Order.query.count(),
            'clients_count': db.session.query(Order.client_id).distinct().count(),
            'subscription_extensions': Order.query.filter_by(is_subscription_extended=True).count()
        }
    
    @staticmethod
    def get_paginated(page: int = 1, per_page: int = 30) -> tuple:
        """Отримує замовлення з пагінацією"""
        pagination = Order.query.order_by(Order.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return pagination.items, pagination.has_next, pagination.total 