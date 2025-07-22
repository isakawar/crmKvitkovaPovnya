#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script for Telegram Bot
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.courier import Courier

def test_bot_initialization():
    """Test if telegram bot initializes correctly"""
    print("🤖 Testing Telegram Bot Initialization...")
    
    app = create_app()
    
    with app.app_context():
        print(f"✅ Flask app created successfully")
        
        # Check if telegram bot is initialized
        if hasattr(app, 'telegram_bot'):
            bot = app.telegram_bot
            print(f"✅ Telegram bot object exists")
            
            if bot.is_initialized():
                print(f"✅ Telegram bot initialized successfully")
                print(f"   - Bot token configured: {'Yes' if app.config.get('TELEGRAM_BOT_TOKEN') else 'No'}")
                print(f"   - Bot application ready: {'Yes' if bot.application else 'No'}")
            else:
                print(f"❌ Telegram bot not fully initialized")
                print(f"   - Check TELEGRAM_BOT_TOKEN in .env file")
        else:
            print(f"❌ Telegram bot not found in app")
        
        # Check database models
        print(f"\n📊 Checking database models...")
        try:
            couriers_count = Courier.query.count()
            print(f"✅ Database connection works")
            print(f"   - Total couriers: {couriers_count}")
            
            # Check for telegram fields
            courier = Courier.query.first()
            if courier:
                has_telegram_fields = hasattr(courier, 'telegram_chat_id')
                print(f"✅ Telegram fields in Courier model: {'Yes' if has_telegram_fields else 'No'}")
            else:
                print(f"ℹ️  No couriers in database to test telegram fields")
                
        except Exception as e:
            print(f"❌ Database error: {e}")

def test_bot_commands():
    """Test basic bot command structure"""
    print(f"\n🎛️  Testing Bot Commands Structure...")
    
    app = create_app()
    
    with app.app_context():
        if hasattr(app, 'telegram_bot') and app.telegram_bot.is_initialized():
            bot = app.telegram_bot
            handlers = bot.handlers
            
            print(f"✅ Bot handlers created")
            print(f"   - Handlers object: {type(handlers).__name__}")
            
            # Check if handlers have required methods
            required_methods = [
                'start_command', 'help_command', 'register_command',
                'profile_command', 'deliveries_command', 'today_command'
            ]
            
            for method in required_methods:
                if hasattr(handlers, method):
                    print(f"   ✅ {method}")
                else:
                    print(f"   ❌ {method} missing")
        else:
            print(f"❌ Bot not initialized, cannot test commands")

def main():
    """Main test function"""
    print("🌸 === ТЕСТУВАННЯ TELEGRAM BOT === 🌸")
    print()
    
    try:
        test_bot_initialization()
        test_bot_commands()
        
        print(f"\n🎉 === ТЕСТУВАННЯ ЗАВЕРШЕНО === 🎉")
        print(f"💡 Для запуску бота в режимі polling:")
        print(f"   python3 scripts/run_telegram_bot.py")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 