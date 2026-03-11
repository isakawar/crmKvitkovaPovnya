# -*- coding: utf-8 -*-
"""
Telegram Notification Service for Kvitkova Povnya CRM
"""

import logging
import asyncio
from typing import List, Optional, Dict

from flask import current_app
from app.models.courier import Courier
from app.models.delivery import Delivery
from app.models.order import Order
from app.telegram_bot.keyboards import CourierKeyboards

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """
    Service for sending notifications to couriers via Telegram
    """
    
    def __init__(self):
        self.keyboards = CourierKeyboards()
    
    def send_delivery_notifications(self, courier: Courier, deliveries: List[Delivery]) -> int:
        """
        Send delivery notifications to courier
        
        Args:
            courier: Courier object
            deliveries: List of deliveries to notify about
            
        Returns:
            Number of successfully sent notifications
        """
        
        if not hasattr(current_app, 'telegram_bot') or not current_app.telegram_bot.is_initialized():
            logger.error("Telegram bot not initialized")
            return 0
        
        if not courier.telegram_chat_id:
            logger.error(f"Courier {courier.name} doesn't have telegram_chat_id")
            return 0
        
        bot = current_app.telegram_bot
        
        try:
            # Запускаємо асинхронну функцію в новому event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                success_count = loop.run_until_complete(
                    self._send_notifications_async(bot, courier, deliveries)
                )
                return success_count
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error sending notifications to courier {courier.name}: {e}")
            return 0
    
    async def _send_notifications_async(self, bot, courier: Courier, deliveries: List[Delivery]) -> int:
        """
        Asynchronously send notifications
        """
        success_count = 0
        
        # Спочатку відправляємо заголовок
        header_message = (
            f"🌸 **Нові доставки на {deliveries[0].delivery_date.strftime('%d.%m.%Y')}**\n\n"
            f"👋 Привіт, {courier.name}!\n"
            f"📦 У вас **{len(deliveries)}** доставок на сьогодні:\n"
        )
        
        try:
            await bot.send_message(
                chat_id=courier.telegram_chat_id,
                text=header_message
            )
        except Exception as e:
            logger.error(f"Failed to send header message to {courier.name}: {e}")
        
        # Відправляємо кожну доставку окремим повідомленням з кнопкою
        for i, delivery in enumerate(deliveries, 1):
            try:
                delivery_message = self._format_delivery_message(delivery, sequence_number=i)
                keyboard = self.keyboards.delivery_actions(delivery.id)
                
                message_id = await bot.send_message(
                    chat_id=courier.telegram_chat_id,
                    text=delivery_message,
                    reply_markup=keyboard
                )
                
                if message_id:
                    # Відмічаємо що повідомлення надіслано
                            # delivery.telegram_notification_sent = True
        # delivery.telegram_message_id = message_id
                    success_count += 1
                    logger.info(f"Sent delivery #{delivery.id} notification to {courier.name}")
                
            except Exception as e:
                logger.error(f"Failed to send delivery #{delivery.id} to {courier.name}: {e}")
        
        # Зберігаємо зміни в базі даних
        from app.extensions import db
        db.session.commit()
        
        # Відправляємо підсумкове повідомлення
        footer_message = (
            f"✅ **Всього відправлено: {success_count} доставок**\n\n"
            f"💡 **Що робити:**\n"
            f"• Натисніть \"✅ Доставлено\" після виконання\n"
            f"• Використовуйте \"❌ Проблема\" якщо виникли труднощі\n"
            f"• Телефонуйте клієнтам перед поїздкою\n\n"
            f"🚗 **Гарної роботи!**"
        )
        
        try:
            await bot.send_message(
                chat_id=courier.telegram_chat_id,
                text=footer_message,
                reply_markup=self.keyboards.back_to_main()
            )
        except Exception as e:
            logger.error(f"Failed to send footer message to {courier.name}: {e}")
        
        return success_count
    
    def _format_delivery_message(self, delivery: Delivery, sequence_number: int = None) -> str:
        """
        Format delivery information for telegram message
        
        Args:
            delivery: Delivery object
            sequence_number: Sequential number for this courier (optional)
            
        Returns:
            Formatted message string
        """
        
        order = delivery.order
        
        # Використовуємо порядковий номер замість ID, якщо він переданий
        if sequence_number:
            header = f"👤{sequence_number}. "
        else:
            header = "👤 "
        
        # Ім'я отримувача
        if order and order.recipient_name:
            message = f"{header}{order.recipient_name}\n"
        else:
            message = f"{header}Не вказано\n"
        
        # Адреса
        if delivery.is_pickup:
            message += f"📍 🏪 Самовивіз\n"
        else:
            address_parts = []
            if order and order.city:
                address_parts.append(order.city)
            if delivery.street:
                address_parts.append(delivery.street)
            if delivery.building_number:
                address_parts.append(delivery.building_number)
            
            address = ", ".join(address_parts)
            message += f"📍 {address}\n"
        
        # Час доставки
        if delivery.time_from and delivery.time_to:
            message += f"🕐 {delivery.time_from} - {delivery.time_to}\n"
        elif delivery.time_from:
            message += f"🕐 після {delivery.time_from}\n"
        elif delivery.time_to:
            message += f"🕐 до {delivery.time_to}\n"
        
        # Телефон
        phone = order.recipient_phone if order else delivery.phone
        if phone:
            message += f"📞 {phone}\n"
        
        # Розмір букета
        size_info = ""
        if order:
            if order.size == 'Власний' and order.custom_amount:
                size_info = f"{order.custom_amount}₴"
            elif order.size:
                size_info = order.size
        elif delivery.bouquet_size:
            size_info = delivery.bouquet_size
        
        if size_info:
            message += f"💐 {size_info}\n"
        
        # Коментар
        comment_text = ""
        if delivery.comment:
            comment_text = delivery.comment
        elif order and order.comment:
            comment_text = order.comment
        
        if comment_text:
            message += f"💬 {comment_text}\n"
        
        return message 