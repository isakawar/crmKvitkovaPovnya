from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    # Створюємо таблиці
    db.create_all()
    
    # Запускаємо seed скрипт
    try:
        from app.scripts.seed_settings import seed_settings
        seed_settings()
        print("Seed дані додано!")
    except Exception as e:
        print(f"Помилка seed: {e}")
    
    print("База даних успішно ініціалізована!") 