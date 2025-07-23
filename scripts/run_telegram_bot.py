#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to run Telegram Bot in polling mode for development and production
"""

import sys
import os
import asyncio
import signal
import logging
import time

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/telegram_bot.log', encoding='utf-8') if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global shutdown_requested
    shutdown_requested = True
    logger.info(f"Received signal {signum}, requesting graceful shutdown...")

def wait_for_database():
    """Wait for database to be ready (useful in Docker)"""
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            app = create_app()
            with app.app_context():
                # Try to access database
                from app.extensions import db
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
                logger.info("Database connection successful")
                return app
        except Exception as e:
            retry_count += 1
            logger.warning(f"Database not ready (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(2)
    
    raise Exception("Could not connect to database after maximum retries")

def main():
    """Main function to run the bot"""
    global shutdown_requested
    
    logger.info("🌸 === ЗАПУСК TELEGRAM BOT === 🌸")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Wait for database and create Flask app
        logger.info("Waiting for database connection...")
        app = wait_for_database()
        
        with app.app_context():
            # Check bot initialization
            if not hasattr(app, 'telegram_bot'):
                logger.error("❌ Telegram bot not found in app")
                return 1
            
            bot = app.telegram_bot
            
            if not bot.is_initialized():
                logger.error("❌ Telegram bot not initialized")
                logger.error("   Check TELEGRAM_BOT_TOKEN environment variable")
                return 1
            
            logger.info("✅ Telegram bot initialized successfully")
            logger.info("📡 Starting polling mode...")
            logger.info("🤖 Bot is ready to receive messages!")
            logger.info("💡 Test commands: /start, /help, /register +380501234567")
            logger.info("🛑 Send SIGTERM or SIGINT to stop the bot")
            
            # Start polling with graceful shutdown handling
            try:
                bot.start_polling()
                
                # Keep the main thread alive until shutdown is requested
                while not shutdown_requested:
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                return 1
            finally:
                logger.info("Stopping bot polling...")
                bot.stop_polling()
                logger.info("🛑 Bot stopped gracefully")
                
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 