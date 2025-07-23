#!/usr/bin/env python3
"""
Скрипт для створення тестових доставок з реалістичними даними
"""

import sys
import os
from datetime import date, datetime, timedelta
import random

# Додаємо шлях до проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.order import Order
from app.models.delivery import Delivery
from app.models.courier import Courier

# Реалістичні дані для генерації
INSTAGRAM_NAMES = [
    "flowers_lover_kyiv", "anna_bouquet", "maria_roses", "oksana_flowers",
    "natasha_bloom", "kateryna_garden", "iryna_petals", "yulia_blossom",
    "svitlana_roses", "olga_flowers", "diana_garden", "tatyana_bloom",
    "viktoria_petals", "liza_flowers", "alina_roses", "sofia_garden",
    "kira_bloom", "mila_petals", "eva_flowers", "daria_roses",
    "nina_garden", "vera_bloom", "lana_flowers", "yana_petals",
    "tina_roses", "rita_garden", "zoya_bloom", "ada_flowers"
]

PHONE_NUMBERS = [
    "+380501234567", "+380671112233", "+380931234567", "+380442223344",
    "+380508887766", "+380679998877", "+380937776655", "+380445554433",
    "+380502221100", "+380676665544", "+380934443322", "+380441110099",
    "+380505556677", "+380672229988", "+380938885566", "+380447774455",
    "+380503334455", "+380677778899", "+380930001122", "+380443336677",
    "+380509990088", "+380671115544", "+380933337799", "+380445552211",
    "+380504445566", "+380678881100", "+380935554477", "+380448887700"
]

STREETS = [
    "вул. Хрещатик", "вул. Саксаганського", "вул. Володимирська", "вул. Льва Толстого",
    "просп. Перемоги", "вул. Антоновича", "вул. Глибочицька", "вул. Оболонський просп.",
    "вул. Героїв Дніпра", "вул. Борщагівська", "вул. Академіка Корольова", "вул. Бориспільська",
    "вул. Лесі Українки", "вул. Велика Васильківська", "вул. Червоноармійська", "вул. Жилянська",
    "вул. Мечникова", "вул. Горького", "вул. Княжий Затон", "вул. Регенераторна",
    "вул. Ревуцького", "вул. Милославська", "вул. Оболонська", "вул. Маршала Малиновського",
    "вул. Драгоманова", "вул. Закревського", "вул. Милютенка", "вул. Гмирі"
]

BUILDING_NUMBERS = [
    "12", "34", "56", "78", "15А", "23Б", "45В", "67Г",
    "89", "101", "123", "145", "167", "189", "201", "223",
    "8", "16", "24", "32", "40", "48", "56", "64", "72", "80"
]

SIZES = ["Мінібукет", "Стандарт", "Міді", "Макі", "Власний"]

COMMENTS = [
    "Дзвонити за 30 хв до доставки",
    "Залишити біля дверей",
    "Передати консьєржу",
    "Красиві троянди, будь ласка",
    "Упаковка в крафт",
    "Доставка на роботу",
    "Сюрприз для дружини",
    "День народження",
    "Річниця весілля",
    "Дзвонити тільки вранці",
    "Домофон не працює",
    "3 поверх, кв. 15",
    "Передати секретарю",
    "Залишити в квітковому магазині внизу",
    "",  # порожній коментар
    "",
    ""
]

PREFERENCES = [
    "Білі троянди",
    "Червоні троянди",
    "Рожеві піони",
    "Мікс кольорів",
    "Без лілій (алергія)",
    "Яскраві кольори",
    "Пастельні тони",
    "Класичний букет",
    "",
    "",
    ""
]

FOR_WHOM = [
    "Дружина", "Дівчина", "Мама", "Сестра", "Подруга",
    "Колега", "Вчителька", "Бабуся", "Себе", "Клієнтка",
    "Партнерка", "Донька", "Тьоща", "Сусідка", "Лікарка"
]

TIME_SLOTS = [
    ("09:00", "12:00"),
    ("12:00", "15:00"),
    ("15:00", "18:00"),
    ("18:00", "21:00"),
    ("10:00", "14:00"),
    ("14:00", "17:00"),
    ("17:00", "20:00"),
    (None, None)  # без часу
]

def create_test_deliveries():
    """Створює тестові доставки на сьогодні та завтра"""
    
    app = create_app()
    
    with app.app_context():
        print("🌸 Створення тестових доставок...")
        
        # Перевіряємо чи є кур'єри
        couriers = Courier.query.all()
        if not couriers:
            print("❌ Спочатку створіть кур'єрів!")
            return
        
        # Дати для створення доставок
        today = date.today()
        tomorrow = today + timedelta(days=1)
        dates = [today, tomorrow]
        
        created_count = 0
        
        for delivery_date in dates:
            # Створюємо 12-15 доставок на кожну дату
            num_deliveries = random.randint(12, 15)
            
            for i in range(num_deliveries):
                # Створюємо клієнта
                instagram = random.choice(INSTAGRAM_NAMES)
                phone = random.choice(PHONE_NUMBERS)
                
                # Перевіряємо чи клієнт уже існує
                client = Client.query.filter_by(instagram=instagram).first()
                if not client:
                    client = Client(
                        instagram=instagram,
                        phone=phone
                    )
                    db.session.add(client)
                    db.session.flush()
                
                # Створюємо замовлення
                size = random.choice(SIZES)
                custom_amount = random.randint(800, 3000) if size == "Власний" else None
                is_pickup = random.random() < 0.3
                
                order = Order(
                    client_id=client.id,
                    recipient_name=instagram.replace('_', ' ').title(),
                    recipient_phone=phone,
                    recipient_social=instagram,
                    city="Київ",
                    street=random.choice(STREETS) if not is_pickup else "Самовивіз",
                    building_number=random.choice(BUILDING_NUMBERS) if not is_pickup else None,
                    is_pickup=is_pickup,
                    delivery_type="One-time",
                    size=size,
                    custom_amount=custom_amount,
                    first_delivery_date=delivery_date,
                    delivery_day=["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"][delivery_date.weekday()],
                    comment=random.choice(COMMENTS),
                    for_whom=random.choice(FOR_WHOM),
                    created_at=datetime.now()
                )
                db.session.add(order)
                db.session.flush()
                
                # Використовуємо ті ж дані що і в замовленні
                street = order.street if not is_pickup else None
                building_number = order.building_number if not is_pickup else None
                
                time_from, time_to = random.choice(TIME_SLOTS)
                
                # Статус: більшість "Очікує", деякі "Розподілено"
                status = "Очікує" if random.random() < 0.7 else "Розподілено"
                courier_id = None
                
                if status == "Розподілено":
                    courier_id = random.choice(couriers).id
                
                delivery = Delivery(
                    order_id=order.id,
                    client_id=client.id,
                    phone=phone,
                    delivery_date=delivery_date,
                    is_pickup=is_pickup,
                    street=street,
                    building_number=building_number,
                    time_from=time_from,
                    time_to=time_to,
                    status=status,
                    courier_id=courier_id,
                    comment=random.choice(COMMENTS),
                    preferences=random.choice(PREFERENCES),
                    size=size
                )
                db.session.add(delivery)
                created_count += 1
        
        # Зберігаємо все
        db.session.commit()
        
        print(f"✅ Створено {created_count} тестових доставок")
        print(f"📅 Дати: {today.strftime('%d.%m.%Y')} та {tomorrow.strftime('%d.%m.%Y')}")
        
        # Показуємо статистику
        total_deliveries = Delivery.query.filter(
            Delivery.delivery_date.in_([today, tomorrow])
        ).count()
        
        pickup_count = Delivery.query.filter(
            Delivery.delivery_date.in_([today, tomorrow]),
            Delivery.is_pickup == True
        ).count()
        
        delivery_count = total_deliveries - pickup_count
        
        print(f"📊 Статистика:")
        print(f"   Всього доставок: {total_deliveries}")
        print(f"   Звичайна доставка: {delivery_count}")
        print(f"   Самовивіз: {pickup_count}")
        print(f"   Сторінка розподілу покаже: {delivery_count} доставок")

if __name__ == "__main__":
    create_test_deliveries() 