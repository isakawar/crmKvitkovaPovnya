import random
import datetime
from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.courier import Courier
from app.models.price import Price
from app.models.order import Order
from app.models.delivery import Delivery

app = create_app()

def seed_data():
    with app.app_context():
        db.session.query(Delivery).delete()
        db.session.query(Order).delete()
        db.session.query(Client).delete()
        db.session.query(Courier).delete()
        db.session.query(Price).delete()
        db.session.commit()

        # 3 кур'єри
        couriers = [
            Courier(name='Влад', phone='380000000001'),
            Courier(name='Іван', phone='380000000002'),
            Courier(name='Олена', phone='380000000003'),
        ]
        db.session.add_all(couriers)
        db.session.commit()

        # 5 букетів
        bouquets = [
            Price(bouquet_size='M', delivery_type='Доставка - підписка', price=300),
            Price(bouquet_size='L', delivery_type='Доставка', price=400),
            Price(bouquet_size='XL', delivery_type='Доставка - підписка', price=500),
            Price(bouquet_size='XXL', delivery_type='Самовивіз', price=600),
            Price(bouquet_size='L', delivery_type='Самовивіз', price=420),
        ]
        db.session.add_all(bouquets)
        db.session.commit()

        # 15 клієнтів і замовлень
        orders = []
        clients = []
        for i in range(15):
            client = Client(
                instagram=f'user{i}',
                phone=f'3800000001{i:02d}',
                city='Київ',
                credits=10000
            )
            db.session.add(client)
            db.session.flush()
            order = Order(
                client_id=client.id,
                street=f'Вулиця {i+1}',
                building_number=str(10+i),
                type=random.choice(['Доставка', 'Самовивіз']),
                bouquet_id=random.choice(bouquets).id,
                delivery_count=random.randint(1, 4),
                bouquet_size=random.choice(['M', 'L', 'XL', 'XXL']),
                delivery_type=random.choice(['Доставка', 'Самовивіз']),
                price_at_order=random.choice([300, 400, 420, 500, 600]),
                created_at=datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 30))
            )
            db.session.add(order)
            db.session.flush()
            orders.append(order)
            clients.append(client)
        db.session.commit()

        # 40 доставок на різні дні
        deliveries = []
        for i in range(40):
            order = random.choice(orders)
            client = next(c for c in clients if c.id == order.client_id)
            bouquet = random.choice(bouquets)
            courier = random.choice(couriers)
            delivery_date = datetime.date.today() - datetime.timedelta(days=random.randint(0, 30))
            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                bouquet_id=bouquet.id,
                delivery_date=delivery_date,
                status=random.choice(['Доставлено', 'Розподілено', 'НП', "Очікує"]),
                street=order.street,
                building_number=order.building_number,
                time_window='10:00-14:00',
                size=bouquet.bouquet_size,
                phone=client.phone,
                courier_id=courier.id,
                bouquet_size=bouquet.bouquet_size,
                delivery_type=bouquet.delivery_type,
                price_at_delivery=bouquet.price,
                delivered_at=datetime.datetime.combine(delivery_date, datetime.time(12, 0)),
                status_changed_at=datetime.datetime.combine(delivery_date, datetime.time(13, 0)),
            )
            db.session.add(delivery)
            deliveries.append(delivery)
        db.session.commit()

        print('Тестові дані успішно створено!')

if __name__ == '__main__':
    seed_data() 