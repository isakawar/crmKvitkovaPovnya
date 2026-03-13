"""
Seed script: 100 test orders for future March dates.
- Kyiv + Kyiv region only
- ~85% courier, ~15% nova_poshta
- ~60% deliveries have preferred time window, ~40% without
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
    "вул. Боженка", "вул. Ямська", "вул. Борщагівська",
    "просп. Науки", "вул. Академіка Вернадського", "вул. Солом'янська",
    "вул. Авіаконструктора Антонова", "вул. Польова", "вул. Теліги",
    "вул. Щусєва", "вул. Ярославська", "вул. Воздвиженська",
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
    ("Вишгород", "вул. Набережна"),
    ("Вишгород", "вул. Шкільна"),
]

NOVA_POSHTA_BRANCHES = [
    ("Київ", "Нова Пошта, відд. №1 (вул. Хрещатик, 22)"),
    ("Київ", "Нова Пошта, відд. №5 (вул. Велика Васильківська, 45)"),
    ("Київ", "Нова Пошта, відд. №12 (просп. Перемоги, 67)"),
    ("Київ", "Нова Пошта, відд. №18 (вул. Борщагівська, 154)"),
    ("Київ", "Нова Пошта, відд. №24 (вул. Лесі Українки, 30)"),
    ("Бровари", "Нова Пошта, відд. №3 (вул. Гагаріна, 15)"),
    ("Ірпінь", "Нова Пошта, відд. №2 (вул. Університетська, 8)"),
    ("Буча", "Нова Пошта, відд. №1 (вул. Яблунська, 20)"),
    ("Бориспіль", "Нова Пошта, відд. №4 (вул. Запорізька, 11)"),
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
    "buttercup_ua", "columbine_kyiv", "sunflower_ua", "pansy_girl",
    "forget_me_not", "bluebell_ua", "candytuft_kyiv", "wallflower_ua",
    "catchfly_girl", "flax_bloom", "spurge_ua", "celandine_kyiv",
    "yarrow_girl", "chamomile_ua", "tansy_bloom", "clary_kyiv",
    "wormwood_ua", "hyssop_girl", "catnip_bloom", "betony_ua",
    "motherwort_kyiv", "selfheal_ua", "agrimony_girl", "vervain_bloom",
    "meadowsweet_ua", "spirea_kyiv", "hawthorn_girl", "elderflower_ua",
    "linden_bloom", "acacia_kyiv", "chestnut_girl", "robinia_ua",
    "wisteria_bloom", "clematis_kyiv", "honeysuckle_ua", "jasmine_girl",
    "mock_orange_ua", "forsythia_kyiv", "deutzia_girl", "weigela_ua",
    "buddleia_bloom", "caryopteris_kyiv", "callicarpa_ua", "vitex_girl",
    "lespedeza_bloom", "indigofera_kyiv", "genista_ua", "cytisus_girl",
    "spartium_bloom", "halimium_kyiv", "cistus_ua", "helianthemum_girl",
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
DISCOUNTS = [None, None, None, "5%", "10%", "15%"]
PERIODICITIES = ["Weekly", "Monthly", "Bi-week", "One-Time"]
SIZES = ["M", "L", "XL", "XXL"]
SIZE_PRICES = {"M": 600, "L": 900, "XL": 1200, "XXL": 1600}
DAYS_UA = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "НД"]
FOR_WHOM = ["Дружина", "Мама", "Подруга", "Сестра", "Колега", "Сам(а)", "Бабуся", "Дочка"]
PREFERENCES = [
    "Без тюльпанів", "Більше зелені", "Пастельні кольори",
    "Яскраві кольори", "Без алергенів", "Улюблені — піони",
    "Тільки білі квіти", "Без троянд",
    None, None, None, None, None,
]

TIME_SLOTS = [
    ("09:00", "12:00"),
    ("10:00", "13:00"),
    ("12:00", "15:00"),
    ("14:00", "17:00"),
    ("15:00", "18:00"),
    ("16:00", "19:00"),
    ("18:00", "21:00"),
]


def random_phone():
    return f"+380{random.randint(50, 99)}{random.randint(1000000, 9999999)}"


def future_march_dates(n: int) -> list[datetime.date]:
    """Returns n dates spread across remaining March days (tomorrow → Mar 31)."""
    today = datetime.date.today()
    start = today + datetime.timedelta(days=1)
    end = datetime.date(today.year, 3, 31)

    if start > end:
        # March already over — use whole month
        start = datetime.date(today.year, 3, 1)

    all_days = []
    d = start
    while d <= end:
        all_days.append(d)
        d += datetime.timedelta(days=1)

    if not all_days:
        all_days = [today + datetime.timedelta(days=i) for i in range(1, n + 1)]

    # Weighted: weekends get 2x more deliveries
    weights = [2 if d.weekday() >= 5 else 1 for d in all_days]
    return random.choices(all_days, weights=weights, k=n)


def clear_all():
    try:
        from app.models.delivery_route import DeliveryRoute, RouteDelivery
        RouteDelivery.query.delete()
        DeliveryRoute.query.delete()
    except Exception:
        pass
    print("Очищення бази даних...")
    Delivery.query.delete()
    Order.query.delete()
    Client.query.delete()
    db.session.commit()
    print("✓ База очищена")


def seed():
    with app.app_context():
        clear_all()

        total = 100
        nova_poshta_count = random.randint(12, 18)   # ~15%
        courier_count = total - nova_poshta_count

        # Shuffle methods: courier or nova_poshta per order
        methods = ['courier'] * courier_count + ['nova_poshta'] * nova_poshta_count
        random.shuffle(methods)

        delivery_dates = future_march_dates(total)

        print(f"Створюємо {total} клієнтів та замовлень...")
        print(f"  Кур'єр: {courier_count}, Нова Пошта: {nova_poshta_count}")

        instagram_pool = INSTAGRAM_NAMES[:total]
        random.shuffle(instagram_pool)

        courier_count_actual = 0
        np_count_actual = 0

        for i in range(total):
            instagram = instagram_pool[i]
            phone = random_phone()
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            recipient_name = f"{first} {last}"
            method = methods[i]
            delivery_date = delivery_dates[i]
            day_of_week = DAYS_UA[delivery_date.weekday()]

            client = Client(
                instagram=f"@{instagram}",
                phone=phone,
                telegram=f"@{instagram}_tg" if random.random() > 0.5 else None,
                credits=random.randint(0, 2),
                marketing_source=random.choice(MARKETING_SOURCES),
                personal_discount=random.choice(DISCOUNTS),
            )
            db.session.add(client)
            db.session.flush()

            size = random.choice(SIZES)
            price = SIZE_PRICES[size]
            periodicity = random.choice(PERIODICITIES)

            if method == 'nova_poshta':
                city, street = random.choice(NOVA_POSHTA_BRANCHES)
                building = None
                floor = None
                entrance = None
                np_count_actual += 1
            else:
                # 70% Kyiv, 30% oblast
                if random.random() < 0.7:
                    city = "Київ"
                    street = random.choice(KYIV_STREETS)
                else:
                    city, street = random.choice(KYIV_OBLAST_ADDRESSES)
                building = str(random.randint(1, 200))
                floor = str(random.randint(1, 25)) if random.random() > 0.35 else None
                entrance = str(random.randint(1, 8)) if floor else None
                courier_count_actual += 1

            # ~60% of deliveries have preferred time window
            has_time = random.random() < 0.60
            if has_time:
                slot = random.choice(TIME_SLOTS)
                time_from, time_to = slot
            else:
                time_from, time_to = None, None

            order = Order(
                client_id=client.id,
                recipient_name=recipient_name,
                recipient_phone=random_phone(),
                recipient_social=f"@{instagram}_recv" if random.random() > 0.6 else None,
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
                time_from=time_from,
                time_to=time_to,
                comment=None,
                preferences=random.choice(PREFERENCES),
                for_whom=random.choice(FOR_WHOM),
                periodicity=periodicity,
                price_at_order=price,
                is_subscription_extended=False,
                delivery_method=method,
            )
            db.session.add(order)
            db.session.flush()

            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                delivery_date=delivery_date,
                status="Очікує",
                street=street,
                building_number=building,
                floor=floor,
                entrance=entrance,
                is_pickup=False,
                time_from=time_from,
                time_to=time_to,
                size=size,
                bouquet_size=size,
                phone=phone,
                delivery_type=periodicity,
                price_at_delivery=price,
                is_subscription=(periodicity != "One-Time"),
                preferences=order.preferences,
                delivery_method=method,
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

        print(f"\n✓ Створено {total} клієнтів, {total} замовлень, {total} доставок")
        print(f"  Кур'єр: {courier_count_actual}, Нова Пошта: {np_count_actual}")


if __name__ == '__main__':
    seed()
