#!/usr/bin/env python3
import os
import sys
from flask import Flask
from flask_migrate import upgrade
from sqlalchemy import text

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, Role

def deploy_auth():
    """
    Розгортає систему авторизації:
    1. Запускає міграції
    2. Створює базові ролі
    3. Створює адміністратора
    """
    print("🔄 Починаємо розгортання авторизації...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Перевіряємо з'єднання з базою даних
            print("📝 Перевіряємо з'єднання з базою даних...")
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            print("✅ З'єднання з базою даних успішне")
            
            # Запускаємо міграції
            print("📝 Запускаємо міграції...")
            upgrade()
            print("✅ Міграції успішно застосовані")
            
            # Створюємо ролі
            print("📝 Створюємо базові ролі...")
            admin_role = Role.query.filter_by(name='admin').first()
            if not admin_role:
                admin_role = Role(name='admin', description='Administrator with full access')
                db.session.add(admin_role)
                print("✅ Створено роль адміністратора")
            
            manager_role = Role.query.filter_by(name='manager').first()
            if not manager_role:
                manager_role = Role(name='manager', description='Manager with limited access')
                db.session.add(manager_role)
                print("✅ Створено роль менеджера")
            
            # Створюємо адміністратора
            print("📝 Створюємо адміністратора...")
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    user_type='admin',
                    is_active=True
                )
                admin.set_password('admin')  # В реальному проекті використовуйте надійний пароль
                admin.roles.append(admin_role)
                db.session.add(admin)
                print("✅ Створено адміністратора (логін: admin, пароль: admin)")
            
            db.session.commit()
            print("✅ Всі зміни успішно збережені")
            
        except Exception as e:
            print(f"❌ Помилка: {e}")
            return 1
    
    print("🎉 Розгортання авторизації успішно завершено!")
    return 0

if __name__ == "__main__":
    exit_code = deploy_auth()
    sys.exit(exit_code) 