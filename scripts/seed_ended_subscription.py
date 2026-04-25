"""
Test script: create a subscription with a past last-delivery date
so it appears in the "Кого потрібно продовжити" section on the dashboard.

Run inside Docker:
  docker compose exec web python scripts/seed_ended_subscription.py

Removes the test data automatically after 60 seconds,
OR run with --cleanup to remove it manually:
  docker compose exec web python scripts/seed_ended_subscription.py --cleanup
"""
import sys
import datetime

sys.path.insert(0, '/app')

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.subscription import Subscription
from app.models.order import Order
from app.models.delivery import Delivery

TEST_INSTAGRAM = '__test_ended_subscription__'

app = create_app()


def cleanup():
    with app.app_context():
        client = Client.query.filter_by(instagram=TEST_INSTAGRAM).first()
        if not client:
            print('Тестовий клієнт не знайдений — нічого видаляти.')
            return
        for sub in client.subscriptions:
            for order in sub.orders:
                Delivery.query.filter_by(order_id=order.id).delete()
                db.session.delete(order)
            db.session.delete(sub)
        db.session.delete(client)
        db.session.commit()
        print('Тестові дані видалено.')


def seed():
    with app.app_context():
        existing = Client.query.filter_by(instagram=TEST_INSTAGRAM).first()
        if existing:
            print('Тестовий клієнт вже існує. Запустіть з --cleanup спочатку.')
            return

        client = Client(
            instagram=TEST_INSTAGRAM,
            name='Тест Закінчена Підписка',
            phone='0000000000',
        )
        db.session.add(client)
        db.session.flush()

        sub = Subscription(
            client_id=client.id,
            type='Weekly',
            status='active',
            delivery_day='СБ',
            recipient_name='Тест Отримувач',
            recipient_phone='0000000000',
            city='Київ',
            street='вул. Тестова',
            building_number='1',
            size='M',
            for_whom='тест',
            is_extended=False,
            followup_status=None,
            delivery_count=4,
        )
        db.session.add(sub)
        db.session.flush()

        # Create 4 orders with deliveries, last one 7 days ago
        today = datetime.date.today()
        for i in range(4):
            delivery_date = today - datetime.timedelta(days=28 - i * 7)
            order = Order(
                client_id=client.id,
                subscription_id=sub.id,
                sequence_number=i + 1,
                size='M',
                city='Київ',
                street='вул. Тестова',
                building_number='1',
                recipient_name='Тест Отримувач',
                recipient_phone='0000000000',
                for_whom='тест',
                delivery_date=delivery_date,
            )
            db.session.add(order)
            db.session.flush()

            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                delivery_date=delivery_date,
                status='Доставлено',
                street='вул. Тестова',
                building_number='1',
                phone='0000000000',
            )
            db.session.add(delivery)

        db.session.commit()
        last_date = today - datetime.timedelta(days=7)
        print(f'Тестовий клієнт створений: {TEST_INSTAGRAM}')
        print(f'Остання доставка: {last_date.strftime("%d.%m.%Y")} (7 днів тому)')
        print('Відкрийте дашборд — клієнт має з\'явитись у черзі "Кого потрібно продовжити".')
        print(f'\nДля видалення: docker compose exec web python scripts/seed_ended_subscription.py --cleanup')


if __name__ == '__main__':
    if '--cleanup' in sys.argv:
        cleanup()
    else:
        seed()
