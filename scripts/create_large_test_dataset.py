#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import random
from datetime import datetime, date, timedelta

# Додаємо шлях до додатку
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.order import Order
from app.models.delivery import Delivery
from app.models.courier import Courier

# Реалістичні дані для України
UKRAINIAN_FEMALE_NAMES = [
    'Анна', 'Марія', 'Олена', 'Ірина', 'Наталія', 'Оксана', 'Віктория', 'Юлія', 'Тетяна', 'Світлана',
    'Валентина', 'Людмила', 'Галина', 'Ніна', 'Лариса', 'Любов', 'Катерина', 'Раїса', 'Тамара', 'Віра',
    'Анастасія', 'Дарія', 'Євгенія', 'Альона', 'Вікторія', 'Діана', 'Кристина', 'Валерія', 'Поліна', 'Софія',
    'Ангеліна', 'Аліна', 'Карина', 'Мілана', 'Вероніка', 'Злата', 'Ярослава', 'Маргарита', 'Емілія', 'Арина'
]

UKRAINIAN_MALE_NAMES = [
    'Олександр', 'Володимир', 'Андрій', 'Сергій', 'Михайло', 'Дмитро', 'Віталій', 'Олег', 'Євген', 'Ігор',
    'Василь', 'Петро', 'Юрій', 'Микола', 'Роман', 'Анатолій', 'Богдан', 'Максим', 'Артем', 'Денис',
    'Ілля', 'Тарас', 'Ростислав', 'Ярослав', 'Матвій', 'Назар', 'Захар', 'Данило', 'Кирило', 'Владислав'
]

UKRAINIAN_SURNAMES = [
    'Петренко', 'Іваненко', 'Шевченко', 'Коваленко', 'Бондаренко', 'Ткаченко', 'Кравченко', 'Мельник',
    'Кравець', 'Шевчук', 'Козлов', 'Іванов', 'Петров', 'Сидоров', 'Москаленко', 'Лисенко', 'Гриценко',
    'Савченко', 'Руденко', 'Марченко', 'Левченко', 'Романенко', 'Кириленко', 'Гончаренко', 'Павленко',
    'Новіков', 'Василенко', 'Поліщук', 'Литвиненко', 'Дорошенко', 'Захаренко', 'Міщенко', 'Бойко'
]

UKRAINIAN_CITIES = [
    'Київ', 'Харків', 'Одеса', 'Дніпро', 'Львів', 'Запоріжжя', 'Кривий Ріг', 'Миколаїв', 'Маріуполь',
    'Луганськ', 'Вінниця', 'Макіївка', 'Севастополь', 'Сімферополь', 'Херсон', 'Полтава', 'Чернігів',
    'Черкаси', 'Житомир', 'Суми', 'Хмельницький', 'Чернівці', 'Горлівка', 'Рівне', 'Кропивницький',
    'Івано-Франківськ', 'Кременчук', 'Тернопіль', 'Луцьк', 'Білгород-Дністровський', 'Краматорськ',
    'Мелітополь', 'Керч', 'Нікополь', 'Слов\'янськ', 'Бердянськ', 'Ужгород', 'Дрогобич', 'Алчевськ',
    'Павлоград', 'Лисичанськ', 'Євпаторія', 'Кам\'янське', 'Александрія', 'Красний Луч', 'Енергодар'
]

KYIV_STREETS = [
    'вул. Хрещатик', 'вул. Саксаганського', 'просп. Перемоги', 'вул. Горького', 'вул. Шота Руставелі',
    'бул. Лесі Українки', 'вул. Володимирська', 'вул. Грушевського', 'просп. Броварський', 'вул. Антоновича',
    'вул. Басейна', 'вул. Велика Васильківська', 'вул. Мала Житомирська', 'вул. Пушкінська', 'вул. Ярославів Вал',
    'вул. Богдана Хмельницького', 'просп. Голосіївський', 'вул. Червоноармійська', 'бул. Шевченка',
    'вул. Костьольна', 'вул. Микільсько-Слобідська', 'вул. Оболонська', 'просп. Оболонський',
    'вул. Чоколівський бул.', 'вул. Димитрова', 'вул. Жилянська', 'вул. Інститутська', 'вул. Прорізна',
    'вул. Турівська', 'вул. Льва Толстого', 'вул. Патриса Лумумби', 'вул. Деревлянська', 'вул. Межигірська'
]

INSTAGRAM_PREFIXES = [
    'flowers_lover', 'beauty_', 'style_', 'kyiv_girl', 'ua_beauty', 'flower_girl', 'insta_',
    'love_flowers', 'bloom_', 'petals_', 'rose_lover', 'floral_', 'bouquet_', 'garden_'
]

TELEGRAM_PREFIXES = [
    '@flower_fan', '@kyiv_style', '@beauty_bloom', '@rose_girl', '@petal_lover', '@bloom_star',
    '@floral_queen', '@garden_fairy', '@bouquet_love', '@flower_magic', '@bloom_beauty'
]

MARKETING_SOURCES = [
    'Таргет', 'Тікток', 'Контент інстаграм', 'Розповіли друзі', 'Побачили офлайн',
    'UGC/блогери', 'Гугл пошук', 'Реклама в Facebook', 'Пошук в Google', 'Рекомендації'
]

DELIVERY_TYPES = ['Weekly', 'Monthly', 'Bi-weekly', 'One-Time']
SIZES = ['M', 'L', 'XL', 'XXL', 'Власний']
FOR_WHOM_OPTIONS = [
    'дівчина собі', 'дівчина іншій дівчині', 'хлопець дівчині', 'хлопець собі',
    'корпоративна підписка', 'весільна підписка', 'хлопець хлопцю'
]

DELIVERY_DAYS = ['Понеділок', 'Вівторок', 'Середа', 'Четвер', 'П\'ятниця', 'Субота', 'Неділя']

PREFERENCES = [
    'Тюльпани', 'Троянди', 'Півонії', 'Лілії', 'Хризантеми', 'Гербери', 'Орхідеї',
    'Яскраві кольори', 'Пастельні тони', 'Білі квіти', 'Червоні квіти', 'Рожеві квіти',
    'Без упаковки', 'Мінімалістична упаковка', 'Святкова упаковка', 'Екологічна упаковка'
]

COMMENTS = [
    'Дуже чекаю доставку!', 'Спасибі за якісний сервіс', 'Завжди свіжі квіти',
    'Рекомендую всім подругам', 'Чудовий сервіс доставки', 'Квіти завжди свіжі та красиві',
    'Дуже задоволена якістю', 'Швидка доставка', 'Гарна упаковка', 'Приємні ціни',
    'Відмінна якість квітів', 'Професійні флористи', 'Завжди вчасно', 'Гарний вибір',
    'Дякую за турботу', 'Прекрасні букети', 'Високий рівень сервісу'
]

def generate_phone():
    """Генерує український номер телефону"""
    operators = ['66', '67', '68', '96', '97', '98', '50', '95', '99', '63', '73', '93']
    operator = random.choice(operators)
    number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"+380{operator}{number}"

def generate_instagram():
    """Генерує Instagram нікнейм"""
    prefix = random.choice(INSTAGRAM_PREFIXES)
    suffix = ''.join([str(random.randint(0, 9)) for _ in range(random.randint(2, 4))])
    return f"{prefix}{suffix}"

def generate_telegram():
    """Генерує Telegram нікнейм"""
    if random.choice([True, False]):  # 50% шансів мати телеграм
        prefix = random.choice(TELEGRAM_PREFIXES)
        suffix = ''.join([str(random.randint(0, 9)) for _ in range(random.randint(2, 3))])
        return f"{prefix}{suffix}"
    return None

def generate_recipient_name():
    """Генерує ім'я отримувача"""
    if random.choice([True, False]):  # 50/50 чоловік/жінка
        name = random.choice(UKRAINIAN_FEMALE_NAMES)
    else:
        name = random.choice(UKRAINIAN_MALE_NAMES)
    
    surname = random.choice(UKRAINIAN_SURNAMES)
    return f"{name} {surname}"

def generate_address():
    """Генерує адресу"""
    street = random.choice(KYIV_STREETS)
    building = random.randint(1, 200)
    
    # Іноді додаємо літеру до номеру будинку
    if random.choice([True, False, False]):  # 33% шансів
        building = f"{building}{random.choice(['А', 'Б', 'В'])}"
    
    floor = None
    entrance = None
    
    # 70% шансів мати поверх і під'їзд
    if random.choice([True, True, True, False]):
        floor = str(random.randint(1, 16))
        entrance = str(random.randint(1, 4))
    
    return street, str(building), floor, entrance

def generate_time_slot():
    """Генерує часовий проміжок доставки"""
    if random.choice([True, False, False]):  # 33% шансів мати конкретний час
        start_hour = random.randint(9, 18)
        end_hour = start_hour + random.randint(1, 3)
        if end_hour > 20:
            end_hour = 20
        return f"{start_hour:02d}:00", f"{end_hour:02d}:00"
    return None, None

def create_clients(count=250):
    """Створює клієнтів"""
    clients = []
    
    print(f"🚀 Створюю {count} клієнтів...")
    
    for i in range(count):
        client = Client(
            instagram=generate_instagram(),
            phone=generate_phone(),
            telegram=generate_telegram(),
            credits=random.randint(0, 2000),
            marketing_source=random.choice(MARKETING_SOURCES),
            personal_discount=str(random.randint(5, 15)) if random.choice([True, False, False]) else None
        )
        clients.append(client)
        
        if (i + 1) % 50 == 0:
            print(f"   ✅ Створено {i + 1}/{count} клієнтів")
    
    # Зберігаємо в базу
    db.session.add_all(clients)
    db.session.commit()
    
    print(f"💾 Збережено {count} клієнтів в базу даних")
    return clients

def create_orders_and_deliveries(clients, order_count=500):
    """Створює замовлення та доставки"""
    orders = []
    deliveries = []
    
    print(f"🛒 Створюю {order_count} замовлень та доставки...")
    
    # Отримуємо кур'єрів для призначення деяких доставок
    couriers = Courier.query.filter_by(active=True).all()
    
    for i in range(order_count):
        client = random.choice(clients)
        
        # Генеруємо дату першої доставки (від сьогодні до +30 днів)
        first_delivery_date = date.today() + timedelta(days=random.randint(0, 30))
        
        street, building, floor, entrance = generate_address()
        time_from, time_to = generate_time_slot()
        
        # Визначаємо розмір та ціну
        size = random.choice(SIZES)
        custom_amount = None
        if size == 'Власний':
            custom_amount = random.randint(800, 5000)
        
        order = Order(
            client_id=client.id,
            recipient_name=generate_recipient_name(),
            recipient_phone=generate_phone(),
            recipient_social=generate_telegram() if random.choice([True, False]) else None,
            city=random.choice(UKRAINIAN_CITIES),
            street=street,
            building_number=building,
            floor=floor,
            entrance=entrance,
            is_pickup=random.choice([True, False, False, False]),  # 25% шансів самовивозу
            delivery_type=random.choice(DELIVERY_TYPES),
            size=size,
            custom_amount=custom_amount,
            first_delivery_date=first_delivery_date,
            delivery_day=random.choice(DELIVERY_DAYS),
            time_from=time_from,
            time_to=time_to,
            comment=random.choice(COMMENTS) if random.choice([True, False]) else None,
            preferences=', '.join(random.sample(PREFERENCES, k=random.randint(1, 3))),
            for_whom=random.choice(FOR_WHOM_OPTIONS)
        )
        orders.append(order)
        
        if (i + 1) % 100 == 0:
            print(f"   ✅ Створено {i + 1}/{order_count} замовлень")
    
    # Зберігаємо замовлення
    db.session.add_all(orders)
    db.session.commit()
    
    print(f"💾 Збережено {order_count} замовлень в базу даних")
    
    # Створюємо доставки для кожного замовлення
    print(f"🚚 Створюю доставки для замовлень...")
    
    delivery_count = 0
    for order in orders:
        if order.delivery_type == 'One-Time':
            # Одноразова доставка
            delivery_count += 1
            delivery = Delivery(
                order_id=order.id,
                client_id=order.client_id,
                delivery_date=order.first_delivery_date,
                street=order.street,
                building_number=order.building_number,
                floor=order.floor,
                entrance=entrance,
                phone=order.recipient_phone,
                time_from=order.time_from,
                time_to=order.time_to,
                size=order.size,
                comment=order.comment,
                is_pickup=order.is_pickup,
                # Призначаємо кур'єру з 60% ймовірністю
                courier_id=random.choice(couriers).id if couriers and random.random() < 0.6 else None
            )
            deliveries.append(delivery)
            
        elif order.delivery_type == 'Weekly':
            # Тижневі доставки (4 доставки)
            for week in range(4):
                delivery_count += 1
                delivery_date = order.first_delivery_date + timedelta(weeks=week)
                delivery = Delivery(
                    order_id=order.id,
                    client_id=order.client_id,
                    delivery_date=delivery_date,
                    street=order.street,
                    building_number=order.building_number,
                    floor=order.floor,
                    entrance=entrance,
                    phone=order.recipient_phone,
                    time_from=order.time_from,
                    time_to=order.time_to,
                    size=order.size,
                    comment=order.comment,
                    is_pickup=order.is_pickup,
                    courier_id=random.choice(couriers).id if couriers and random.random() < 0.6 else None
                )
                deliveries.append(delivery)
                
        elif order.delivery_type == 'Bi-weekly':
            # Доставки кожні 2 тижні (2 доставки)
            for period in range(2):
                delivery_count += 1
                delivery_date = order.first_delivery_date + timedelta(weeks=period*2)
                delivery = Delivery(
                    order_id=order.id,
                    client_id=order.client_id,
                    delivery_date=delivery_date,
                    street=order.street,
                    building_number=order.building_number,
                    floor=order.floor,
                    entrance=entrance,
                    phone=order.recipient_phone,
                    time_from=order.time_from,
                    time_to=order.time_to,
                    size=order.size,
                    comment=order.comment,
                    is_pickup=order.is_pickup,
                    courier_id=random.choice(couriers).id if couriers and random.random() < 0.6 else None
                )
                deliveries.append(delivery)
                
        elif order.delivery_type == 'Monthly':
            # Місячні доставки (1 доставка)
            delivery_count += 1
            delivery = Delivery(
                order_id=order.id,
                client_id=order.client_id,
                delivery_date=order.first_delivery_date,
                street=order.street,
                building_number=order.building_number,
                floor=order.floor,
                entrance=entrance,
                phone=order.recipient_phone,
                time_from=order.time_from,
                time_to=order.time_to,
                size=order.size,
                comment=order.comment,
                is_pickup=order.is_pickup,
                courier_id=random.choice(couriers).id if couriers and random.random() < 0.6 else None
            )
            deliveries.append(delivery)
    
    # Зберігаємо доставки
    db.session.add_all(deliveries)
    db.session.commit()
    
    print(f"💾 Збережено {delivery_count} доставок в базу даних")
    return orders, deliveries

def main():
    """Головна функція"""
    app = create_app()
    
    with app.app_context():
        print("🌸 === ГЕНЕРАЦІЯ ВЕЛИКОГО ТЕСТОВОГО ДАТАСЕТУ === 🌸")
        print("📊 Створюватиму:")
        print("   • 250 клієнтів з реалістичними даними")
        print("   • 500 замовлень різних типів")
        print("   • Відповідні доставки для кожного замовлення")
        print("   • Призначення частини доставок кур'єрам")
        print()
        
        # Перевіряємо чи є кур'єри
        courier_count = Courier.query.filter_by(active=True).count()
        print(f"📦 Знайдено {courier_count} активних кур'єрів для призначення доставок")
        print()
        
        start_time = datetime.now()
        
        # Створюємо клієнтів
        clients = create_clients(250)
        
        # Створюємо замовлення та доставки
        orders, deliveries = create_orders_and_deliveries(clients, 500)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print()
        print("🎉 === ГЕНЕРАЦІЯ ЗАВЕРШЕНА === 🎉")
        print(f"⏱️  Час виконання: {duration.total_seconds():.1f} секунд")
        print(f"👥 Створено клієнтів: {len(clients)}")
        print(f"🛒 Створено замовлень: {len(orders)}")
        print(f"🚚 Створено доставок: {len(deliveries)}")
        print()
        print("📈 Статистика доставок за типами:")
        
        delivery_types_count = {}
        for order in orders:
            if order.delivery_type not in delivery_types_count:
                delivery_types_count[order.delivery_type] = 0
            delivery_types_count[order.delivery_type] += 1
        
        for delivery_type, count in delivery_types_count.items():
            print(f"   • {delivery_type}: {count} замовлень")
        
        assigned_deliveries = sum(1 for delivery in deliveries if delivery.courier_id)
        unassigned_deliveries = len(deliveries) - assigned_deliveries
        
        print()
        print("🚚 Статистика призначення доставок:")
        print(f"   • Призначено кур'єрам: {assigned_deliveries}")
        print(f"   • Не призначено: {unassigned_deliveries}")
        print()
        print("✅ Датасет готовий для тестування!")

if __name__ == '__main__':
    main() 