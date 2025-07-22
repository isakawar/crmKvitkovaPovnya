# -*- coding: utf-8 -*-
"""
Telegram Bot package for Kvitkova Povnya CRM

This package handles all Telegram bot functionality for couriers:
- Registration and authentication
- Delivery notifications
- Status updates
- Integration with CRM system
"""

from .bot import TelegramBot

__all__ = ['TelegramBot'] 