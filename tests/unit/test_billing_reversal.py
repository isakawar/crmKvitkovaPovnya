"""Сторно списання за доставку.

Списання за доставку було однобічним: статус «Доставлено» знімав гроші з
балансу клієнта, а повернення в «Скасовано»/«Очікує» їх не повертало. Оскільки
статус міняє кур'єр із телеграм-бота, помилковий тап лишав баланс зміщеним
назавжди — і, оскільки звіт «Баланс клієнтів» рахує історію назад від
``client.credits``, зсув переписував усі попередні місяці.

Сторно — окремий рядок ``delivery_charge`` з від'ємною сумою поточною датою.
Через це «чи списано за доставку» — питання про НЕТТО-суму, а не про існування
рядка.
"""
import datetime
from decimal import Decimal

from app.models import Client, Order, Delivery
from app.models.transaction import Transaction
from app.services.billing_service import (
    charge_delivery,
    net_charged_for_delivery,
    reverse_delivery_charge,
)
from app.services.delivery_service import set_delivery_status
from app.extensions import db


def _one_time_order(session, client, charged_amount=500, status='Розподілено'):
    order = Order(
        client_id=client.id, recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', is_pickup=False, delivery_method='courier',
        size='M', delivery_date=datetime.date.today(), for_whom='Дружина',
        charged_amount=charged_amount,
    )
    session.add(order)
    session.flush()
    delivery = Delivery(
        order_id=order.id, client_id=client.id, delivery_date=order.delivery_date,
        status=status, size='M', phone='+380991234567', delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return order, delivery


def test_reversal_restores_client_balance(app, session):
    client = Client(instagram='rev_1', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    charge_delivery(delivery)
    session.commit()
    assert client.credits == Decimal('-500')

    reverse_delivery_charge(delivery)
    session.commit()

    assert client.credits == Decimal('0')
    assert net_charged_for_delivery(delivery.id) == 0


def test_reversal_keeps_original_row_and_adds_a_negative_one(app, session):
    client = Client(instagram='rev_2', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    charge_delivery(delivery)
    session.commit()
    reverse_delivery_charge(delivery)
    session.commit()

    rows = Transaction.query.filter_by(delivery_id=delivery.id).order_by(Transaction.id).all()
    assert [r.amount for r in rows] == [Decimal('500'), Decimal('-500')]
    # Сторно проводиться поточною датою — закритий місяць не переписується.
    assert rows[1].date == datetime.date.today()
    assert 'Сторно' in rows[1].comment


def test_reversal_is_idempotent(app, session):
    client = Client(instagram='rev_3', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    charge_delivery(delivery)
    session.commit()
    reverse_delivery_charge(delivery)
    session.commit()
    assert reverse_delivery_charge(delivery) is None
    session.commit()

    assert client.credits == Decimal('0')
    assert Transaction.query.filter_by(delivery_id=delivery.id).count() == 2


def test_reversal_on_nothing_charged_is_noop(app, session):
    client = Client(instagram='rev_4', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    assert reverse_delivery_charge(delivery) is None
    assert client.credits == Decimal('0')


def test_undelivering_via_status_change_refunds(app, session):
    """Повний шлях: статус → списання → відкат статусу → сторно."""
    client = Client(instagram='rev_5', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    set_delivery_status(delivery, 'Доставлено')
    assert client.credits == Decimal('-500')
    assert delivery.delivered_at is not None

    set_delivery_status(delivery, 'Скасовано')

    assert client.credits == Decimal('0')
    # delivered_at скинуто, щоб повторне проведення виставило актуальний час
    assert delivery.delivered_at is None


def test_redelivering_after_reversal_charges_again(app, session):
    """Після сторно нетто == 0, тож повторне «Доставлено» знову списує."""
    client = Client(instagram='rev_6', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    set_delivery_status(delivery, 'Доставлено')
    set_delivery_status(delivery, 'Очікує')
    assert client.credits == Decimal('0')

    set_delivery_status(delivery, 'Доставлено')

    assert client.credits == Decimal('-500')
    assert net_charged_for_delivery(delivery.id) == Decimal('500')


def test_double_delivered_does_not_double_charge(app, session):
    """Захист від подвійного списання лишився на місці."""
    client = Client(instagram='rev_7', credits=Decimal('0'))
    session.add(client)
    session.commit()
    _, delivery = _one_time_order(session, client)

    set_delivery_status(delivery, 'Доставлено')
    set_delivery_status(delivery, 'Доставлено')

    assert client.credits == Decimal('-500')
    assert Transaction.query.filter_by(delivery_id=delivery.id).count() == 1
