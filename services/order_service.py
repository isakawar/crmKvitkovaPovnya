from models import db, Client, Order, Price, Delivery
import datetime

WEEKDAY_MAP = {'пн':0, 'вт':1, 'ср':2, 'чт':3, 'пт':4, 'сб':5, 'нд':6}

def get_or_create_client(phone, city, instagram):
    client = Client.query.filter_by(phone=phone).first()
    if not client:
        client = Client(phone=phone, city=city, instagram=instagram or '')
        db.session.add(client)
        db.session.commit()
    else:
        if client.city != city:
            client.city = city
        if instagram and client.instagram != instagram:
            client.instagram = instagram
        db.session.commit()
    return client

def check_and_spend_credits(client, bouquet, delivery_count):
    credits_needed = bouquet.price * delivery_count if bouquet else 0
    if client.credits < credits_needed:
        return False, credits_needed
    client.credits -= credits_needed
    db.session.commit()
    return True, credits_needed

def create_order_and_deliveries(client, form):
    delivery_count = int(form.get('delivery_count', 1))
    bouquet_id = form.get('bouquet_id')
    bouquet = Price.query.get(bouquet_id) if bouquet_id else None
    order = Order(
        client_id=client.id,
        street=form['street'],
        building_number=form['building_number'],
        floor=form.get('floor'),
        entrance=form['entrance'],
        size=form.get('size'),
        type=form['type'],
        comment=form['comment'],
        time_window=form.get('time_window'),
        bouquet_id=bouquet_id,
        delivery_count=delivery_count,
        recipient_phone=form.get('recipient_phone'),
        periodicity=form.get('periodicity'),
        preferred_days=','.join(form.getlist('preferred_days')),
        time_from=form.get('time_from'),
        time_to=form.get('time_to')
    )
    db.session.add(order)
    db.session.commit()
    # Доставки
    preferred_days = form.getlist('preferred_days')
    days = [WEEKDAY_MAP[d] for d in preferred_days if d in WEEKDAY_MAP]
    if not days:
        days = [datetime.date.today().weekday()]
    periodicity = form.get('periodicity') or '1/7'
    start_date = datetime.date.today()
    created = 0
    i = 0
    while created < delivery_count:
        d_date = start_date + datetime.timedelta(days=i)
        if d_date.weekday() in days:
            if periodicity == '1/14' and created > 0:
                d_date = d_date + datetime.timedelta(days=7*(created))
            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                bouquet_id=bouquet.id if bouquet else None,
                delivery_date=d_date,
                status='Очікує',
                comment=form.get('comment', ''),
                street=order.street,
                building_number=order.building_number,
                time_window=order.time_window,
                size=order.size,
                phone=order.recipient_phone
            )
            db.session.add(delivery)
            created += 1
        i += 1
    db.session.commit()
    return order 