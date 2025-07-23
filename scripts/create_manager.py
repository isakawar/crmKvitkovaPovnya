from app import create_app
from app.extensions import db
from app.models import User, Role
from app.models.user import ROLE_MANAGER

def create_manager():
    app = create_app()
    with app.app_context():
        # Створюємо роль менеджера, якщо вона не існує
        manager_role = Role.query.filter_by(name=ROLE_MANAGER).first()
        if not manager_role:
            manager_role = Role(name=ROLE_MANAGER, description='Manager with limited access')
            db.session.add(manager_role)
            print("Створено роль менеджера")
        
        # Створюємо менеджера, якщо він не існує
        manager = User.query.filter_by(username='manager').first()
        if not manager:
            manager = User(
                username='manager',
                email='manager@example.com',
                user_type='manager',
                is_active=True
            )
            manager.set_password('manager')
            manager.roles.append(manager_role)
            db.session.add(manager)
            print("Створено менеджера з логіном 'manager' та паролем 'manager'")
        else:
            # Якщо менеджер існує, оновлюємо його пароль
            manager.set_password('manager')
            if manager_role not in manager.roles:
                manager.roles.append(manager_role)
            print("Оновлено пароль існуючого менеджера")
        
        db.session.commit()
        print("Операцію успішно завершено!")

if __name__ == '__main__':
    create_manager() 