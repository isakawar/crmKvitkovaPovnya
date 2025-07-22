#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to run Telegram Bot in polling mode for development
"""

import sys
import os
import asyncio
import signal
import logging

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping bot...")
    sys.exit(0)

def main():
    """Main function to run the bot"""
    print("🌸 === ЗАПУСК TELEGRAM BOT === 🌸")
    print()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create Flask app
        app = create_app()
        
        with app.app_context():
            # Check bot initialization
            if not hasattr(app, 'telegram_bot'):
                print("❌ Telegram bot not found in app")
                return
            
            bot = app.telegram_bot
            
            if not bot.is_initialized():
                print("❌ Telegram bot not initialized")
                print("   Check TELEGRAM_BOT_TOKEN in .env file")
                return
            
            print("✅ Telegram bot initialized successfully")
            print(f"📡 Starting polling mode...")
            print(f"🤖 Bot is ready to receive messages!")
            print()
            print("💡 Test commands:")
            print("   /start - Start interaction with bot")
            print("   /help - Show help message")
            print("   /register +380501234567 - Register courier")
            print()
            print("🛑 Press Ctrl+C to stop the bot")
            print("=" * 50)
            
            # Start polling
            bot.start_polling()
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 