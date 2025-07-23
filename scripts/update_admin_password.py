from app import create_app
from app.extensions import db
from app.models import User
import getpass

def update_admin_password():
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Адміністратора не знайдено!")
            return
        
        while True:
            password = getpass.getpass("Введіть новий пароль: ")
            confirm_password = getpass.getpass("Підтвердіть новий пароль: ")
            
            if password != confirm_password:
                print("Паролі не співпадають! Спробуйте ще раз.")
                continue
            
            if len(password) < 8:
                print("Пароль повинен містити мінімум 8 символів! Спробуйте ще раз.")
                continue
            
            admin.set_password(password)
            db.session.commit()
            print("Пароль успішно оновлено!")
            break

if __name__ == '__main__':
    update_admin_password() 