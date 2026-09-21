"""Канонічні значення доменних «переліків» (статуси, типи, розміри).

Навіщо цей модуль
-----------------
У БД усі ці поля — вільні ``varchar`` без CHECK-констрейнтів, а значення були
розкидані по коду сирими літералами (180+ входжень українських рядків). Через це
в таблиці ``transaction`` уже завівся п'ятий тип ``adjustment``, про який не знав
ані докстрінг моделі, ані ``transaction_service.delete_transaction`` — і саме
через це видалення коригування тихо ламало баланс клієнта.

Модуль лишається єдиним місцем, де ці рядки оголошені. DB-рівневих
CHECK-констрейнтів свідомо ще немає: спершу треба побачити, які значення реально
лежать у проді (``flask audit-enum-values``), і лише тоді вішати констрейнт
окремою міграцією — інакше вона впаде на деплої.

Значення — саме ті рядки, що вже лежать у БД. Міняти їх не можна без міграції даних.
"""

# ── Delivery.status ────────────────────────────────────────────────────────────
DELIVERY_PENDING = 'Очікує'
DELIVERY_ASSIGNED = 'Розподілено'
DELIVERY_DONE = 'Доставлено'
DELIVERY_CANCELLED = 'Скасовано'

DELIVERY_STATUSES = frozenset({
    DELIVERY_PENDING, DELIVERY_ASSIGNED, DELIVERY_DONE, DELIVERY_CANCELLED,
})

#: Статуси, після яких доставку більше не чіпають автоматичні пересинхронізації
#: (перенос дат, копіювання полів із замовлення, перерахунок ціни).
DELIVERY_TERMINAL_STATUSES = frozenset({DELIVERY_DONE, DELIVERY_CANCELLED})


# ── Delivery.florist_status ────────────────────────────────────────────────────
FLORIST_APPROVED = 'Затверджено'
FLORIST_ASSEMBLED = 'Зібрано'
FLORIST_HANDED_OVER = "Передано кур'єру"
FLORIST_REJECTED = 'Відхилено'

FLORIST_STATUSES = frozenset({
    FLORIST_APPROVED, FLORIST_ASSEMBLED, FLORIST_HANDED_OVER, FLORIST_REJECTED,
})

#: Флористичні статуси, які означають «у роботі на сьогодні» (бейдж у навбарі).
FLORIST_ACTIVE_STATUSES = (FLORIST_APPROVED, FLORIST_ASSEMBLED, FLORIST_HANDED_OVER)


# ── Transaction.transaction_type ───────────────────────────────────────────────
TXN_CREDIT = 'credit'                    # оплата від клієнта (+ до балансу)
TXN_DEBIT = 'debit'                      # витрата компанії (в P&L)
TXN_DELIVERY_CHARGE = 'delivery_charge'  # списання за доставку (− з балансу)
TXN_TRANSFER = 'transfer'                # переказ між рахунками
TXN_ADJUSTMENT = 'adjustment'            # ручне коригування балансу клієнта

TRANSACTION_TYPES = frozenset({
    TXN_CREDIT, TXN_DEBIT, TXN_DELIVERY_CHARGE, TXN_TRANSFER, TXN_ADJUSTMENT,
})

#: Типи, що впливають на ``client.credits``, і знак цього впливу.
#: Використовується всюди, де транзакцію створюють, редагують або видаляють, щоб
#: жоден шлях не міг зсунути баланс однобічно.
BALANCE_SIGN_BY_TXN_TYPE = {
    TXN_CREDIT: +1,
    TXN_ADJUSTMENT: +1,
    TXN_DELIVERY_CHARGE: -1,
}


def balance_delta(transaction_type, amount):
    """Наскільки ``client.credits`` має зміститись від транзакції даного типу.

    Повертає 0 для типів, що балансу клієнта не стосуються (``debit``,
    ``transfer``), тож викликати можна беззастережно для будь-якої транзакції.
    """
    return (amount or 0) * BALANCE_SIGN_BY_TXN_TYPE.get(transaction_type, 0)


# ── Transaction.payment_type ───────────────────────────────────────────────────
PAYMENT_MONOBANK = 'monobank'
PAYMENT_CASH = 'cash'

PAYMENT_TYPES = frozenset({PAYMENT_MONOBANK, PAYMENT_CASH})


# ── Subscription.status ────────────────────────────────────────────────────────
SUBSCRIPTION_ACTIVE = 'active'
SUBSCRIPTION_COMPLETED = 'completed'
SUBSCRIPTION_CANCELLED = 'cancelled'
SUBSCRIPTION_DRAFT = 'draft'

SUBSCRIPTION_STATUSES = frozenset({
    SUBSCRIPTION_ACTIVE, SUBSCRIPTION_COMPLETED, SUBSCRIPTION_CANCELLED, SUBSCRIPTION_DRAFT,
})

#: Subscription.type — періодичність. Історично живе і в ``order_service`` як
#: ``SUBSCRIPTION_TYPES``; тут — канонічне джерело.
SUBSCRIPTION_WEEKLY = 'Weekly'
SUBSCRIPTION_BIWEEKLY = 'Bi-weekly'
SUBSCRIPTION_MONTHLY = 'Monthly'

SUBSCRIPTION_TYPES = ['Weekly', 'Monthly', 'Bi-weekly']


# ── DeliveryRoute.status ───────────────────────────────────────────────────────
ROUTE_DRAFT = 'draft'
ROUTE_SENT = 'sent'
ROUTE_ACCEPTED = 'accepted'
ROUTE_REJECTED = 'rejected'
ROUTE_COMPLETED = 'completed'

ROUTE_STATUSES = frozenset({
    ROUTE_DRAFT, ROUTE_SENT, ROUTE_ACCEPTED, ROUTE_REJECTED, ROUTE_COMPLETED,
})


# ── Order.delivery_method / Subscription.delivery_method ───────────────────────
DELIVERY_METHOD_COURIER = 'courier'
DELIVERY_METHOD_NOVA_POSHTA = 'nova_poshta'

DELIVERY_METHODS = frozenset({DELIVERY_METHOD_COURIER, DELIVERY_METHOD_NOVA_POSHTA})


# ── Order.size ─────────────────────────────────────────────────────────────────
SIZE_CUSTOM = 'Власний'

#: Розміри, доступні «з коробки». Реальний перелік редагується в Налаштуваннях
#: (``Settings(type='size')``), тож це базовий набір, а не закритий перелік —
#: валідувати розмір за ним не можна.
DEFAULT_SIZES = ('S', 'M', 'L', 'XL', 'XXL', SIZE_CUSTOM)


# ── Certificate ────────────────────────────────────────────────────────────────
CERT_TYPE_AMOUNT = 'amount'
CERT_TYPE_SIZE = 'size'
CERT_TYPE_SUBSCRIPTION = 'subscription'

CERTIFICATE_TYPES = frozenset({CERT_TYPE_AMOUNT, CERT_TYPE_SIZE, CERT_TYPE_SUBSCRIPTION})

CERT_ACTIVE = 'active'
CERT_USED = 'used'
CERT_EXPIRED = 'expired'

CERTIFICATE_STATUSES = frozenset({CERT_ACTIVE, CERT_USED, CERT_EXPIRED})


# ── Settings.type ──────────────────────────────────────────────────────────────
#: ``settings`` — універсальний довідник; ``type`` розрізняє, що саме в рядку.
SETTING_SIZE = 'size'
SETTING_EXPENSE_TYPE = 'expense_type'
SETTING_PAYMENT_ACCOUNT = 'payment_account'
SETTING_FEATURE_FLAG = 'feature_flag'


#: Опис полів для ``flask audit-enum-values``: (модель, атрибут, дозволені значення).
#: Перелічені тут пари — це рівно ті поля, які колись мають отримати
#: CHECK-констрейнт; спершу треба переконатись, що прод чистий.
def enum_fields():
    """Повертає [(label, column, allowed_set)] для аудиту фактичних значень у БД."""
    from app.models import Delivery, Order
    from app.models.subscription import Subscription
    from app.models.transaction import Transaction
    from app.models.delivery_route import DeliveryRoute
    from app.models.certificate import Certificate

    return [
        ('delivery.status', Delivery.status, DELIVERY_STATUSES),
        ('delivery.florist_status', Delivery.florist_status, FLORIST_STATUSES),
        ('delivery.delivery_method', Delivery.delivery_method, DELIVERY_METHODS),
        ('order.delivery_method', Order.delivery_method, DELIVERY_METHODS),
        ('subscription.status', Subscription.status, SUBSCRIPTION_STATUSES),
        ('subscription.type', Subscription.type, frozenset(SUBSCRIPTION_TYPES)),
        ('transaction.transaction_type', Transaction.transaction_type, TRANSACTION_TYPES),
        ('transaction.payment_type', Transaction.payment_type, PAYMENT_TYPES),
        ('delivery_routes.status', DeliveryRoute.status, ROUTE_STATUSES),
        ('certificates.type', Certificate.type, CERTIFICATE_TYPES),
        ('certificates.status', Certificate.status, CERTIFICATE_STATUSES),
    ]
