"""
Seed script: 50 test clients + 50 subscriptions with deliveries for current month.
Delivery distribution: most days have 1-5 deliveries, some days have 10-30.
"""
import sys
import random
import datetime

sys.path.insert(0, '/app')

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.order import Order
from app.models.delivery import Delivery

app = create_app()

# ── Data pools ─────────────────────────────────────────────────────────────────

KYIV_STREETS = [
    "вул. Хрещатик", "вул. Велика Васильківська", "вул. Саксаганського",
    "вул. Льва Толстого", "вул. Антоновича", "вул. Симона Петлюри",
    "вул. Шота Руставелі", "бул. Тараса Шевченка", "вул. Лесі Українки",
    "вул. Олеся Гончара", "вул. Гетьмана", "просп. Перемоги",
    "просп. Бандери", "вул. Дорогожицька", "вул. Кирилівська",
    "вул. Глибочицька", "вул. Артема", "вул. Жилянська",
    "вул. Димитрова", "вул. Боженка", "вул. Ямська",
    "вул. Борщагівська", "просп. Науки", "вул. Академіка Вернадського",
    "вул. Солом'янська", "вул. Авіаконструктора Антонова",
]

KYIV_OBLAST_ADDRESSES = [
    ("Бровари", "вул. Незалежності"),
    ("Бровари", "вул. Гагаріна"),
    ("Бровари", "просп. Незалежності"),
    ("Ірпінь", "вул. Університетська"),
    ("Ірпінь", "вул. Шевченка"),
    ("Буча", "вул. Яблунська"),
    ("Буча", "вул. Вокзальна"),
    ("Вишневе", "вул. Київська"),
    ("Вишневе", "вул. Соборна"),
    ("Бориспіль", "вул. Героїв Небесної Сотні"),
    ("Бориспіль", "вул. Запорізька"),
    ("Фастів", "вул. Центральна"),
    ("Васильків", "вул. Соборна"),
    ("Обухів", "вул. Київська"),
]

INSTAGRAM_NAMES = [
    "lily_blooms", "rose_dreams", "flower_lover_ua", "sunny_petals",
    "kvitkova_ua", "bouquet_life", "flora_kyiv", "petal_queen",
    "bloom_girl", "tulip_magic", "violet_sky", "daisylove",
    "orchid_fan", "fresh_flowers", "nature_beauty", "spring_blossoms",
    "floral_mood", "garden_life", "green_petals", "wild_flowers",
    "romance_blooms", "love_bouquet", "sweet_lavender", "poppy_field",
    "chrysanthemum_ua", "jasmine_dreams", "lilac_time", "magnolia_girl",
    "peony_lover", "iris_queen", "aster_world", "dahliya_ua",
    "freesia_kyiv", "zinnia_fan", "marigold_mood", "cosmos_flowers",
    "snapdragon_ua", "verbena_girl", "heather_bloom", "clover_life",
    "hyacinth_ua", "narcissus_dream", "cornflower_ua", "anemone_kyiv",
    "primrose_girl", "foxglove_ua", "larkspur_love", "delphinium_ua",
    "buttercup_ua", "columbine_kyiv",
]

FIRST_NAMES = [
    "Оксана", "Марія", "Наталія", "Олена", "Юлія", "Ірина", "Тетяна",
    "Людмила", "Катерина", "Вікторія", "Анна", "Світлана", "Олга",
    "Валентина", "Лариса", "Тамара", "Ганна", "Діана", "Христина",
    "Дарина", "Аліна", "Поліна", "Антоніна", "Надія", "Галина",
    "Зоя", "Ніна", "Лідія", "Вера", "Таїсія",
]

LAST_NAMES = [
    "Шевченко", "Коваленко", "Бондаренко", "Мельник", "Кравченко",
    "Олійник", "Ткаченко", "Іваненко", "Лисенко", "Марченко",
    "Петренко", "Захаренко", "Романенко", "Сидоренко", "Василенко",
    "Гриценко", "Бойко", "Клименко", "Руденко", "Пономаренко",
]

MARKETING_SOURCES = ["Instagram", "TikTok", "Telegram", "Рекомендація", "Google", "Viber"]
DISCOUNTS = [None, "5%", "10%", "15%"]
PERIODICITIES = ["Weekly", "Monthly", "Bi-week"]
SIZES = ["M", "L", "XL"]
SIZE_PRICES = {"M": 600, "L": 900, "XL": 1200}
DAYS_UA = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "НД"]
FOR_WHOM = ["Дружина", "Мама", "Подруга", "Сестра", "Колега", "Сам(а)", "Бабуся"]
PREFERENCES = [
    "Без тюльпанів", "Більше зелені", "Пастельні кольори",
    "Яскраві кольори", "Без алергенів", "Улюблені — піони",
    None, None, None,
]

TIME_SLOTS = [
    ("09:00", "12:00"),
    ("10:00", "13:00"),
    ("12:00", "15:00"),
    ("14:00", "17:00"),
    ("15:00", "18:00"),
    ("16:00", "19:00"),
]


def random_phone():
    return f"+380{random.randint(50,99)}{random.randint(1000000,9999999)}"


def build_delivery_calendar(year: int, month: int) -> list[datetime.date]:
    """
    Returns a list of dates for the current month.
    Some days get heavy load (10-30), rest get 1-5.
    Total ≈ 50.
    """
    import calendar
    _, days_in_month = calendar.monthrange(year, month)
    all_days = [datetime.date(year, month, d) for d in range(1, days_in_month + 1)]

    # Pick 2-3 heavy days
    heavy_days = random.sample(all_days, k=3)
    heavy_counts = {d: random.randint(10, 30) for d in heavy_days}

    # Fill remaining from other days to reach exactly 50
    total_heavy = sum(heavy_counts.values())
    remaining = max(50 - total_heavy, 0)

    other_days = [d for d in all_days if d not in heavy_days]
    light_days = random.sample(other_days, k=min(remaining, len(other_days)))
    # distribute 1-5 per light day, cap at remaining
    light_schedule = []
    left = remaining
    for d in light_days:
        if left <= 0:
            break
        count = min(random.randint(1, 5), left)
        light_schedule.extend([d] * count)
        left -= count

    schedule = []
    for d, cnt in heavy_counts.items():
        schedule.extend([d] * cnt)
    schedule.extend(light_schedule)

    return schedule


def clear_all():
    from app.models.delivery_route import DeliveryRoute, RouteDelivery
    print("Очищення бази даних...")
    RouteDelivery.query.delete()
    DeliveryRoute.query.delete()
    Delivery.query.delete()
    Order.query.delete()
    Client.query.delete()
    db.session.commit()
    print("✓ База очищена")


def seed():
    with app.app_context():
        clear_all()
        today = datetime.date.today()
        year, month = today.year, today.month

        delivery_dates = build_delivery_calendar(year, month)
        random.shuffle(delivery_dates)
        # Trim or pad to exactly 50
        if len(delivery_dates) > 50:
            delivery_dates = delivery_dates[:50]
        while len(delivery_dates) < 50:
            delivery_dates.append(datetime.date(year, month, random.randint(1, today.day)))

        print(f"Створюємо 50 клієнтів та 50 підписок...")

        for i in range(50):
            instagram = INSTAGRAM_NAMES[i]
            phone = random_phone()
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            recipient_name = f"{first} {last}"

            # Client
            client = Client(
                instagram=f"@{instagram}",
                phone=phone,
                telegram=f"@{instagram}_tg" if random.random() > 0.4 else None,
                credits=random.randint(0, 3),
                marketing_source=random.choice(MARKETING_SOURCES),
                personal_discount=random.choice(DISCOUNTS),
            )
            db.session.add(client)
            db.session.flush()  # get client.id

            # Address: 70% Kyiv, 30% oblast
            if random.random() < 0.7:
                city = "Київ"
                street = random.choice(KYIV_STREETS)
            else:
                city, street = random.choice(KYIV_OBLAST_ADDRESSES)

            building = str(random.randint(1, 150))
            floor = str(random.randint(1, 25)) if random.random() > 0.3 else None
            entrance = str(random.randint(1, 8)) if floor else None

            size = random.choice(SIZES)
            price = SIZE_PRICES[size]
            periodicity = random.choice(PERIODICITIES)
            delivery_date = delivery_dates[i]
            day_of_week = DAYS_UA[delivery_date.weekday()]
            slot = random.choice(TIME_SLOTS)

            order = Order(
                client_id=client.id,
                recipient_name=recipient_name,
                recipient_phone=random_phone(),
                recipient_social=f"@{instagram}_recv" if random.random() > 0.5 else None,
                city=city,
                street=street,
                building_number=building,
                floor=floor,
                entrance=entrance,
                is_pickup=False,
                delivery_type=periodicity,
                size=size,
                bouquet_size=size,
                first_delivery_date=delivery_date,
                delivery_day=day_of_week,
                time_from=slot[0],
                time_to=slot[1],
                comment=None,
                preferences=random.choice(PREFERENCES),
                for_whom=random.choice(FOR_WHOM),
                periodicity=periodicity,
                price_at_order=price,
                is_subscription_extended=False,
            )
            db.session.add(order)
            db.session.flush()

            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                delivery_date=delivery_date,
                status="Очікує" if delivery_date >= today else random.choice(["Доставлено", "Доставлено", "Скасовано"]),
                street=street,
                building_number=building,
                floor=floor,
                entrance=entrance,
                is_pickup=False,
                time_from=slot[0],
                time_to=slot[1],
                size=size,
                bouquet_size=size,
                phone=phone,
                delivery_type=periodicity,
                price_at_delivery=price,
                is_subscription=True,
                preferences=order.preferences,
            )
            db.session.add(delivery)

        db.session.commit()

        # Summary
        from collections import Counter
        date_counts = Counter(delivery_dates)
        print("\nРозподіл доставок по датах:")
        for d in sorted(date_counts):
            bar = "█" * date_counts[d]
            print(f"  {d.strftime('%d.%m')} ({DAYS_UA[d.weekday()]}): {date_counts[d]:2d}  {bar}")

        print(f"\n✓ Створено 50 клієнтів, 50 замовлень, 50 доставок")


if __name__ == '__main__':
    seed()
