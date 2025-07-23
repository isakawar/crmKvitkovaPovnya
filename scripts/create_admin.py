from app import create_app
from app.extensions import db
from app.models import User, Role

def create_admin():
    app = create_app()
    with app.app_context():
        # Створюємо роль адміністратора, якщо вона не існує
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrator with full access')
            db.session.add(admin_role)
        
        # Створюємо адміністратора, якщо він не існує
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
        
        db.session.commit()
        print("Admin user created successfully!")

if __name__ == '__main__':
    create_admin() 