# -*- coding: utf-8 -*-
"""
Telegram Bot Services for Kvitkova Povnya CRM
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.models.courier import Courier
from app.models.delivery import Delivery
from app.models.order import Order
from app.models.client import Client
from app.extensions import db

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Service class for telegram bot business logic
    """
    
    @staticmethod
    def get_courier_deliveries(courier: Courier, period: str = "all") -> List[Delivery]:
        """
        Get courier deliveries for specified period
        
        Args:
            courier: Courier object
            period: "today", "tomorrow", "week", "all"
            
        Returns:
            List of Delivery objects
        """
        today = datetime.now().date()
        base_query = Delivery.query.filter_by(courier_id=courier.id).filter(Delivery.status != 'Скасовано')
        
        if period == "today":
            return base_query.filter_by(delivery_date=today).all()
        elif period == "tomorrow":
            tomorrow = today + timedelta(days=1)
            return base_query.filter_by(delivery_date=tomorrow).all()
        elif period == "week":
            week_end = today + timedelta(days=7)
            return base_query.filter(Delivery.delivery_date.between(today, week_end)).all()
        else:  # all
            return base_query.all()
    
    @staticmethod
    def format_delivery_info(delivery: Delivery, detailed: bool = False) -> str:
        """
        Format delivery information for telegram message
        
        Args:
            delivery: Delivery object
            detailed: Include detailed information
            
        Returns:
            Formatted string
        """
        # Get related data
        order = delivery.order
        client = delivery.client
        
        # Status emoji
        status_emoji = {
            'Очікує': '⏳',
            'Доставлено': '✅',
            'Скасовано': '❌'
        }.get(delivery.status, '❓')
        
        # Basic info
        text = f"{status_emoji} **Доставка #{delivery.id}**\n"
        text += f"📅 {delivery.delivery_date.strftime('%d.%m.%Y')}\n"
        
        if delivery.is_pickup:
            text += f"📍 **Самовивіз**\n"
        else:
            address = f"{delivery.street}"
            if delivery.building_number:
                address += f" {delivery.building_number}"
            if delivery.floor:
                address += f", {delivery.floor} поверх"
            if delivery.entrance:
                address += f", під'їзд {delivery.entrance}"
            text += f"📍 {address}\n"
        
        # Time
        if delivery.time_from and delivery.time_to:
            text += f"🕐 {delivery.time_from} - {delivery.time_to}\n"
        
        # Contact
        text += f"👤 {order.recipient_name}\n"
        text += f"📞 {delivery.phone}\n"
        
        # Size and type
        if delivery.bouquet_size:
            text += f"💐 {delivery.bouquet_size}\n"
        
        if detailed:
            # Additional details
            if order.recipient_social:
                text += f"📱 {order.recipient_social}\n"
            
            if delivery.comment:
                text += f"💬 {delivery.comment}\n"
            
            if delivery.preferences:
                text += f"⭐ {delivery.preferences}\n"
            
            # Price
            if delivery.price_at_delivery:
                text += f"💰 {delivery.price_at_delivery}₴\n"
            
            # Client info
            text += f"\n👥 **Клієнт:** {client.name}\n"
            if client.marketing_source:
                text += f"📢 Джерело: {client.marketing_source}\n"
        
        return text
    
    @staticmethod
    def mark_delivery_completed(delivery_id: int, courier: Courier) -> bool:
        """
        Mark delivery as completed
        
        Args:
            delivery_id: Delivery ID
            courier: Courier object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            delivery = Delivery.query.filter_by(
                id=delivery_id, 
                courier_id=courier.id
            ).first()
            
            if not delivery:
                logger.error(f"Delivery {delivery_id} not found for courier {courier.id}")
                return False
            
            if delivery.status == 'Доставлено':
                logger.warning(f"Delivery {delivery_id} already completed")
                return True
            
            # Update delivery status
            delivery.status = 'Доставлено'
            delivery.delivered_at = datetime.utcnow()
            delivery.status_changed_at = datetime.utcnow()
            
            # Update courier statistics
            if delivery.status != 'Доставлено':  # Avoid double counting
                courier.deliveries_count += 1
            
            db.session.commit()
            
            logger.info(f"Delivery {delivery_id} marked as completed by courier {courier.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking delivery {delivery_id} as completed: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def report_delivery_problem(delivery_id: int, courier: Courier, problem_type: str, comment: str = None) -> bool:
        """
        Report problem with delivery
        
        Args:
            delivery_id: Delivery ID
            courier: Courier object
            problem_type: Type of problem
            comment: Optional comment
            
        Returns:
            True if successful, False otherwise
        """
        try:
            delivery = Delivery.query.filter_by(
                id=delivery_id, 
                courier_id=courier.id
            ).first()
            
            if not delivery:
                logger.error(f"Delivery {delivery_id} not found for courier {courier.id}")
                return False
            
            # Add problem to delivery comment
            problem_text = f"[ПРОБЛЕМА - {datetime.now().strftime('%d.%m %H:%M')}] {problem_type}"
            if comment:
                problem_text += f": {comment}"
            
            if delivery.comment:
                delivery.comment += f"\n{problem_text}"
            else:
                delivery.comment = problem_text
            
            delivery.status_changed_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"Problem reported for delivery {delivery_id} by courier {courier.id}: {problem_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error reporting problem for delivery {delivery_id}: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_delivery_statistics(courier: Courier) -> dict:
        """
        Get delivery statistics for courier
        
        Args:
            courier: Courier object
            
        Returns:
            Dictionary with statistics
        """
        today = datetime.now().date()
        
        # All deliveries
        all_deliveries = Delivery.query.filter_by(courier_id=courier.id).all()
        
        # Filter by status
        completed = [d for d in all_deliveries if d.status == 'Доставлено']
        pending = [d for d in all_deliveries if d.status == 'Очікує']
        cancelled = [d for d in all_deliveries if d.status == 'Скасовано']
        
        # Today's deliveries
        today_deliveries = [d for d in all_deliveries if d.delivery_date == today]
        today_completed = [d for d in today_deliveries if d.status == 'Доставлено']
        today_pending = [d for d in today_deliveries if d.status == 'Очікує']
        
        # This week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_deliveries = [d for d in all_deliveries 
                          if week_start <= d.delivery_date <= week_end]
        week_completed = [d for d in week_deliveries if d.status == 'Доставлено']
        
        # This month
        month_start = today.replace(day=1)
        month_deliveries = [d for d in all_deliveries 
                           if d.delivery_date >= month_start]
        month_completed = [d for d in month_deliveries if d.status == 'Доставлено']
        
        return {
            'total_deliveries': len(all_deliveries),
            'completed': len(completed),
            'pending': len(pending),
            'cancelled': len(cancelled),
            'today_total': len(today_deliveries),
            'today_completed': len(today_completed),
            'today_pending': len(today_pending),
            'week_total': len(week_deliveries),
            'week_completed': len(week_completed),
            'month_total': len(month_deliveries),
            'month_completed': len(month_completed),
            'completion_rate': round(len(completed) / len(all_deliveries) * 100, 1) if all_deliveries else 0
        }
    
    @staticmethod
    def update_telegram_notification_status(delivery_id: int, message_id: int = None, sent: bool = True) -> bool:
        """
        Update telegram notification status for delivery
        
        Args:
            delivery_id: Delivery ID
            message_id: Telegram message ID
            sent: Whether notification was sent
            
        Returns:
            True if successful, False otherwise
        """
        try:
            delivery = Delivery.query.get(delivery_id)
            if not delivery:
                logger.error(f"Delivery {delivery_id} not found")
                return False
            
            delivery.telegram_notification_sent = sent
            if message_id:
                delivery.telegram_message_id = message_id
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating telegram notification status for delivery {delivery_id}: {e}")
            db.session.rollback()
            return False 