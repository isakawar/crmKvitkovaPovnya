import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.extensions import db
from app.models.settings import Settings

app = create_app()

with app.app_context():
    data = [
        # Міста
        ('city', 'Київ'),
        ('city', 'Полтава'),
        ('city', 'Вишгород'),
        ('city', 'Бровари'),
        ('city', 'Буча'),
        # Тип доставки
        ('delivery_type', 'Weekly'),
        ('delivery_type', 'Monthly'),
        ('delivery_type', 'Bi-weekly'),
        ('delivery_type', 'One-Time'),
        # Розміри
        ('size', 'M'),
        ('size', 'L'),
        ('size', 'XL'),
        ('size', 'XXL'),
        ('size', 'Власний'),
        # Для кого
        ('for_whom', 'дівчина собі'),
        ('for_whom', 'дівчина іншій дівчині'),
        ('for_whom', 'хлопець дівчині'),
        ('for_whom', 'хлопець собі'),
        ('for_whom', 'корпоративна підписка'),
        ('for_whom', 'весільна підписка'),
        ('for_whom', 'хлопець хлопцю'),
        # Звідки дізнались
        ('marketing_source', 'Таргет'),
        ('marketing_source', 'Тікток'),
        ('marketing_source', 'Контент інстаграм'),
        ('marketing_source', 'Розповіли друзі'),
        ('marketing_source', 'Побачили офлайн'),
        ('marketing_source', 'UGC/блогери'),
        ('marketing_source', 'Гугл пошук'),
        # Типи витрат
        ('expense_type', 'Квіти'),
        ('expense_type', 'Залишки квітів'),
        ('expense_type', 'Пакування'),
        ('expense_type', 'Вази'),
        ('expense_type', 'Ножиці'),
        ('expense_type', 'Доставка'),
        ('expense_type', 'Доставка квітів'),
        ('expense_type', 'Підживлення для квітів'),
        ('expense_type', 'реклама Facebook'),
        ('expense_type', 'Реклама (блогери)'),
        ('expense_type', 'сервіси'),
        ('expense_type', 'Тестові букети'),
        ('expense_type', 'рекламні букети'),
        ('expense_type', 'букет комплімент'),
        ('expense_type', 'Нова пошта'),
        ('expense_type', 'Іжа та напої'),
        ('expense_type', 'Інші витрати'),
        ('expense_type', 'оренда офісу'),
        ('expense_type', 'комунальні'),
        ('expense_type', 'інтернет'),
        ('expense_type', 'Меблі та інше'),
        ('expense_type', 'Амортизація'),
        ('expense_type', 'Клінінг'),
        ('expense_type', 'Флорист №1 (Аня)'),
        ('expense_type', 'Флорист №2 (Наталя)'),
        ('expense_type', 'ТікТок (Наталі)'),
        ('expense_type', 'Client Manager (Паханчік)'),
        ('expense_type', 'SMM'),
        ('expense_type', 'Таргетолог'),
        ('expense_type', 'Еквайрінг'),
        ('expense_type', 'Податок'),
    ]
    added_count = 0
    for t, v in data:
        if not Settings.query.filter_by(type=t, value=v).first():
            db.session.add(Settings(type=t, value=v))
            added_count += 1
            print(f"Added: {t} = {v}")
        else:
            print(f"Already exists: {t} = {v}")
    db.session.commit()
    print(f'Seeded settings! Added {added_count} new records.') 