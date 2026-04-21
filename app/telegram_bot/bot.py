# -*- coding: utf-8 -*-
"""
Main Telegram Bot class for Kvitkova Povnya CRM
"""

import logging
from typing import Optional
from telegram import Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from .handlers import CourierHandlers
from .keyboards import CourierKeyboards

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Main Telegram Bot class for courier management
    """
    
    def __init__(self, app=None):
        self.app = None
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.handlers = None
        self.keyboards = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the bot with Flask app"""
        self.app = app
        
        # Get bot token from config
        bot_token = app.config.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not found in config. Bot will not be initialized.")
            return
        
        # Initialize bot application
        self.application = Application.builder().token(bot_token).build()
        self.bot = self.application.bot
        
        # Initialize handlers and keyboards
        self.handlers = CourierHandlers(self)
        self.keyboards = CourierKeyboards()
        
        # Register command handlers
        self._register_handlers()
        
        logger.info("Telegram Bot initialized successfully")
    
    def _register_handlers(self):
        """Register all bot command and callback handlers"""
        if not self.application:
            return
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("register", self.handlers.register_command))
        
        # Callback query handlers (for inline keyboard buttons)
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback_query))
        
        # Contact sharing handler (courier verification)
        self.application.add_handler(MessageHandler(filters.CONTACT, self.handlers.handle_contact))

        # Message handlers (for text messages)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.handle_text_message))
        
        logger.info("Bot handlers registered successfully")
    
    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> Optional[int]:
        """
        Send message to specific chat
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            reply_markup: Optional keyboard markup
            
        Returns:
            Message ID if successful, None otherwise
        """
        try:
            if not self.bot:
                logger.error("Bot not initialized")
                return None
                
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return message.message_id
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return None
    
    async def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup=None) -> bool:
        """
        Edit existing message
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            text: New message text
            reply_markup: Optional keyboard markup
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.bot:
                logger.error("Bot not initialized")
                return False
                
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return True
        except Exception as e:
            logger.error(f"Failed to edit message {message_id} in chat {chat_id}: {e}")
            return False
    
    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """
        Delete message
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.bot:
                logger.error("Bot not initialized")
                return False
                
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete message {message_id} in chat {chat_id}: {e}")
            return False
    
    def start_polling(self):
        """Start bot polling for development"""
        if not self.application:
            logger.error("Bot application not initialized")
            return
            
        logger.info("Starting bot polling...")
        self.application.run_polling()
    
    async def set_webhook(self, webhook_url: str, secret_token: str = None):
        """Set webhook for production"""
        if not self.bot:
            logger.error("Bot not initialized")
            return False
            
        try:
            await self.bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token
            )
            logger.info(f"Webhook set successfully: {webhook_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            return False
    
    def is_initialized(self) -> bool:
        """Check if bot is properly initialized"""
        return self.application is not None and self.bot is not None 