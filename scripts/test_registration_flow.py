#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to demonstrate courier registration flow
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.courier import Courier
from app.extensions import db

def test_registration_scenarios():
    """Test different registration scenarios"""
    
    print("🧪 === ТЕСТУВАННЯ СЦЕНАРІЇВ РЕЄСТРАЦІЇ === 🧪")
    print()
    
    app = create_app()
    
    with app.app_context():
        
        # Scenario 1: Create test courier
        print("📋 **СЦЕНАРІЙ 1: Створення кур'єра в CRM**")
        
        # Check if test courier exists
        test_phone = "+380999888777"
        test_courier = Courier.query.filter_by(phone=test_phone).first()
        
        if test_courier:
            print(f"   ℹ️  Тестовий кур'єр вже існує: {test_courier.name}")
        else:
            # Create test courier
            test_courier = Courier(
                name="Тестовий Кур'єр",
                phone=test_phone,
                active=True,
                delivery_rate=60
            )
            db.session.add(test_courier)
            db.session.commit()
            print(f"   ✅ Створено тестового кур'єра: {test_courier.name}")
        
        print(f"   📱 Телефон: {test_courier.phone}")
        print(f"   🔧 Статус: {'Активний' if test_courier.active else 'Неактивний'}")
        print(f"   💰 Рейт: {test_courier.delivery_rate}₴")
        print()
        
        # Scenario 2: Show existing couriers
        print("📋 **СЦЕНАРІЙ 2: Існуючі кур'єри в системі**")
        all_couriers = Courier.query.all()
        
        for courier in all_couriers:
            status = "🟢 Активний" if courier.active else "🔴 Неактивний"
            telegram_status = "📱 Підключено" if courier.telegram_registered else "⭕ Не підключено"
            
            print(f"   • {courier.name} ({courier.phone}) - {status} - {telegram_status}")
            if courier.telegram_username:
                print(f"     └── Telegram: @{courier.telegram_username}")
        
        print()
        
        # Scenario 3: Registration instructions
        print("📋 **СЦЕНАРІЙ 3: Інструкції для тестування**")
        print()
        print("🤖 **Для тестування реєстрації в Telegram боті:**")
        print()
        print("1️⃣ **Успішна реєстрація:**")
        print(f"   /register {test_courier.phone}")
        print("   → Повинен зареєструвати успішно")
        print()
        
        print("2️⃣ **Неіснуючий номер:**")
        print("   /register +380111111111")
        print("   → Повідомлення що кур'єр не знайдений")
        print()
        
        print("3️⃣ **Неправильний формат:**")
        print("   /register 380501234567")
        print("   → Помилка формату номера")
        print()
        
        print("4️⃣ **Тестування деактивації:**")
        print("   - Деактивуйте кур'єра в CRM")
        print(f"   - Спробуйте /register {test_courier.phone}")
        print("   → Повідомлення про деактивований акаунт")
        print()
        
        print("5️⃣ **Тестування скидання прив'язки:**")
        print("   - Зареєструйте кур'єра в боті")
        print("   - Скиньте прив'язку в CRM")
        print("   - Спробуйте зареєструватися знову")
        print()
        
        # Scenario 4: Show CRM URL
        print("📋 **СЦЕНАРІЙ 4: Управління в CRM**")
        print()
        print("🌐 **Відкрийте веб-інтерфейс CRM:**")
        print("   http://localhost:5055/couriers")
        print()
        print("✨ **Нові функції на сторінці кур'єрів:**")
        print("   • Колонка 'Telegram' показує статус підключення")
        print("   • Кнопка 'Скинути прив'язку' для переприв'язки")
        print("   • Відображення Telegram username'ів")
        print("   • Контроль доступу через активацію/деактивацію")
        print()

def main():
    """Main test function"""
    try:
        test_registration_scenarios()
        
        print("🎉 **ТЕСТУВАННЯ ГОТОВЕ!**")
        print()
        print("💡 **Послідовність тестування:**")
        print("1. Запустіть CRM: python3 run.py")
        print("2. Відкрийте http://localhost:5055/couriers")
        print("3. Створіть кур'єра або використайте існуючого")
        print("4. Протестуйте реєстрацію в Telegram боті")
        print("5. Спробуйте скинути прив'язку в CRM")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 