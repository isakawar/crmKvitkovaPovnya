"""
Seed script: add orders spread across the last 5 months for trend chart testing.

Run:
  docker compose exec web python3 scripts/seed_orders_trend.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import date, datetime, timedelta

random.seed(99)


def month_start(d):
    return date(d.year, d.month, 1)


def next_month(d):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def rand_datetime_in_month(m):
    end = next_month(m) - timedelta(days=1)
    d = m + timedelta(days=random.randint(0, (end - m).days))
    return datetime(d.year, d.month, d.day,
                    random.randint(8, 21), random.randint(0, 59))


def main():
    from app import create_app
    app = create_app()

    with app.app_context():
        from app.extensions import db
        from app.models.order import Order
        from app.models import Client

        today = date.today()

        # Build list of months: 5 months back up to (but not including) current month
        months = []
        cur = month_start(today)
        for _ in range(5):
            cur_prev = month_start(cur - timedelta(days=1))
            months.insert(0, cur_prev)
            cur = cur_prev

        clients = Client.query.all()
        if not clients:
            print("ERROR: no clients found — seed clients first.")
            return

        cities = ['Київ', 'Львів', 'Одеса', 'Харків', 'Дніпро']
        streets = ['Хрещатик', 'Велика Васильківська', 'Саксаганського',
                   'Лесі Українки', 'Антоновича', 'Шота Руставелі']
        sizes = ['S', 'M', 'L', 'XL', 'XXL']
        for_whom_options = ['Дружина', 'Мама', 'Подруга', 'Колега', 'Сестра', 'Дівчина']

        # Realistic monthly counts: growth trend, dip, recovery
        counts_per_month = [18, 25, 22, 30, 28]

        total_created = 0
        for month, count in zip(months, counts_per_month):
            for _ in range(count):
                client = random.choice(clients)
                created = rand_datetime_in_month(month)
                delivery_date = created.date() + timedelta(days=random.randint(1, 14))

                order = Order(
                    client_id=client.id,
                    recipient_name=client.name or 'Тестовий отримувач',
                    recipient_phone=client.phone or '+380000000000',
                    city=random.choice(cities),
                    street=random.choice(streets),
                    building_number=str(random.randint(1, 120)),
                    size=random.choice(sizes),
                    delivery_date=delivery_date,
                    for_whom=random.choice(for_whom_options),
                    delivery_method=random.choices(['courier', 'nova_poshta'], weights=[80, 20])[0],
                    created_at=created,
                )
                db.session.add(order)
                total_created += 1

        db.session.commit()
        print(f"Done. {total_created} orders created across {len(months)} months:")
        for month, count in zip(months, counts_per_month):
            print(f"  {month.strftime('%Y-%m')}: {count} orders")


if __name__ == '__main__':
    main()
