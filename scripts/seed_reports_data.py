"""
Seed script: test data for /reports statistics.
Deliveries: 4 months back + 2 months forward from today.
Transactions: monthly credits & debits across the same 6-month window.

Run:
  docker compose exec web python3 scripts/seed_reports_data.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import date, timedelta

random.seed(42)


def month_start(d):
    return date(d.year, d.month, 1)


def next_month(d):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def months_range(start, count):
    cur = month_start(start)
    for _ in range(count):
        yield cur
        cur = next_month(cur)


def rand_date_in_month(m):
    end = next_month(m) - timedelta(days=1)
    return m + timedelta(days=random.randint(0, (end - m).days))


def main():
    from app import create_app
    app = create_app()

    with app.app_context():
        from app.extensions import db
        from app.models import Order, Client
        from app.models.delivery import Delivery
        from app.models.transaction import Transaction

        today = date.today()
        window_start = month_start(today - timedelta(days=4 * 30))  # ~4 months back
        # 4 past months + current month + 2 future months = 7 months total
        all_months = list(months_range(window_start, 7))

        # ── Gather existing data ──────────────────────────────────────────────
        orders = Order.query.all()
        if not orders:
            print("ERROR: no orders found — seed orders first.")
            return

        order_pairs = [(o.id, o.client_id) for o in orders]

        # Expense type settings by id (from existing data)
        # Salary
        salary_ids = [120, 121]
        # Delivery
        delivery_ids = [102, 103, 111]
        # Uncategorized expense types
        other_expense_ids = [97, 98, 99, 100, 104, 105, 106, 107,
                              108, 109, 112, 113, 114, 115, 116,
                              117, 118, 119, 122, 123, 125, 126, 127]

        # ── Deliveries ────────────────────────────────────────────────────────
        print("Creating deliveries...")
        deliveries_created = 0

        for month in all_months:
            is_future = month > month_start(today)
            count = random.randint(18, 35)

            for _ in range(count):
                order_id, client_id = random.choice(order_pairs)
                d = rand_date_in_month(month)

                if is_future:
                    status = random.choices(
                        ['Очікує', 'Доставлено', 'Скасовано'],
                        weights=[75, 15, 10]
                    )[0]
                else:
                    status = random.choices(
                        ['Доставлено', 'Скасовано', 'Очікує'],
                        weights=[78, 12, 10]
                    )[0]

                delivery = Delivery(
                    order_id=order_id,
                    client_id=client_id,
                    delivery_date=d,
                    status=status,
                    street=random.choice(['Хрещатик', 'Велика Васильківська', 'Саксаганського',
                                          'Лесі Українки', 'Антоновича', 'Шота Руставелі']),
                    building_number=str(random.randint(1, 120)),
                    size=random.choice(['S', 'M', 'L', 'XL', 'XXL']),
                    is_pickup=random.random() < 0.1,
                    delivery_method=random.choices(['courier', 'nova_poshta'], weights=[85, 15])[0],
                )
                db.session.add(delivery)
                deliveries_created += 1

        db.session.commit()
        print(f"  ✓ {deliveries_created} deliveries created")

        # ── Transactions ──────────────────────────────────────────────────────
        print("Creating transactions...")
        credits_created = 0
        debits_created = 0

        past_months = [m for m in all_months if m <= month_start(today)]

        for month in past_months:
            is_current = month == month_start(today)
            # Fewer transactions in current (partially elapsed) month
            credit_count = random.randint(22, 40) if not is_current else random.randint(8, 18)

            # ── Credits (revenue) ────────────────────────────────────────────
            for _ in range(credit_count):
                amount = random.choice([
                    random.randint(500, 900),
                    random.randint(900, 1500),
                    random.randint(1500, 2500),
                    random.randint(2500, 4000),
                ])
                client_id = random.choice([p[1] for p in order_pairs])
                t = Transaction(
                    transaction_type='credit',
                    client_id=client_id,
                    amount=amount,
                    payment_type=random.choices(['monobank', 'cash'], weights=[70, 30])[0],
                    date=rand_date_in_month(month),
                    comment=random.choice([None, None, None,
                                           'Замовлення букету', 'Передплата підписки',
                                           'Оплата доставки', 'Подарунковий сертифікат']),
                )
                db.session.add(t)
                credits_created += 1

            # ── Debits (expenses) ────────────────────────────────────────────

            # Salary — once per florist per month
            for sid in salary_ids:
                amount = random.randint(14000, 22000)
                pay_day = month.replace(day=random.choice([1, 2, 3, 5]))
                t = Transaction(
                    transaction_type='debit',
                    amount=amount,
                    expense_type_id=sid,
                    date=pay_day,
                    comment='Зарплата',
                )
                db.session.add(t)
                debits_created += 1

            # Delivery costs — multiple per month
            delivery_count = random.randint(8, 18)
            for _ in range(delivery_count):
                sid = random.choice(delivery_ids)
                amount = random.randint(180, 650)
                t = Transaction(
                    transaction_type='debit',
                    amount=amount,
                    expense_type_id=sid,
                    date=rand_date_in_month(month),
                    comment=random.choice(['Кур\'єр', 'Нова Пошта', 'Доставка']),
                )
                db.session.add(t)
                debits_created += 1

            # Flowers & supplies — bulk purchases
            flowers_purchases = random.randint(2, 4)
            for _ in range(flowers_purchases):
                amount = random.randint(3500, 14000)
                t = Transaction(
                    transaction_type='debit',
                    amount=amount,
                    expense_type_id=97,  # Квіти
                    date=rand_date_in_month(month),
                    comment=random.choice(['Троянди', 'Піони', 'Ліліє', 'Евкаліпт', 'Хризантеми']),
                )
                db.session.add(t)
                debits_created += 1

            # Packaging
            t = Transaction(
                transaction_type='debit',
                amount=random.randint(800, 2800),
                expense_type_id=99,  # Пакування
                date=rand_date_in_month(month),
                comment='Пакувальні матеріали',
            )
            db.session.add(t)
            debits_created += 1

            # Office rent — fixed
            t = Transaction(
                transaction_type='debit',
                amount=7500,
                expense_type_id=114,  # Оренда офісу
                date=month.replace(day=1),
                comment='Оренда',
            )
            db.session.add(t)
            debits_created += 1

            # Utilities
            t = Transaction(
                transaction_type='debit',
                amount=random.randint(1200, 2600),
                expense_type_id=115,  # Комунальні
                date=rand_date_in_month(month),
                comment='Комунальні послуги',
            )
            db.session.add(t)
            debits_created += 1

            # Ads — Facebook / bloggers
            for ad_id in [105, 106]:
                if random.random() < 0.8:
                    t = Transaction(
                        transaction_type='debit',
                        amount=random.randint(1500, 5000),
                        expense_type_id=ad_id,
                        date=rand_date_in_month(month),
                        comment='Реклама',
                    )
                    db.session.add(t)
                    debits_created += 1

            # TikTok / target
            for ad_id in [122, 125]:
                if random.random() < 0.6:
                    t = Transaction(
                        transaction_type='debit',
                        amount=random.randint(1000, 3500),
                        expense_type_id=ad_id,
                        date=rand_date_in_month(month),
                        comment='Таргет / TikTok',
                    )
                    db.session.add(t)
                    debits_created += 1

            # Services & internet
            t = Transaction(
                transaction_type='debit',
                amount=random.randint(400, 1200),
                expense_type_id=107,  # Сервіси
                date=rand_date_in_month(month),
                comment='SaaS / підписки',
            )
            db.session.add(t)
            debits_created += 1

            t = Transaction(
                transaction_type='debit',
                amount=random.randint(250, 550),
                expense_type_id=116,  # Інтернет
                date=month.replace(day=random.randint(3, 7)),
                comment='Інтернет',
            )
            db.session.add(t)
            debits_created += 1

            # Acquiring fee + tax
            t = Transaction(
                transaction_type='debit',
                amount=random.randint(600, 1800),
                expense_type_id=126,  # Еквайрінг
                date=rand_date_in_month(month),
                comment='Комісія банку',
            )
            db.session.add(t)
            debits_created += 1

            t = Transaction(
                transaction_type='debit',
                amount=random.randint(1800, 4500),
                expense_type_id=127,  # Податок
                date=rand_date_in_month(month),
                comment='ФОП податок',
            )
            db.session.add(t)
            debits_created += 1

            # Random one-off expenses
            one_off_count = random.randint(1, 4)
            for _ in range(one_off_count):
                sid = random.choice(other_expense_ids)
                amount = random.randint(200, 3000)
                t = Transaction(
                    transaction_type='debit',
                    amount=amount,
                    expense_type_id=sid,
                    date=rand_date_in_month(month),
                )
                db.session.add(t)
                debits_created += 1

        db.session.commit()
        print(f"  ✓ {credits_created} credit transactions created")
        print(f"  ✓ {debits_created} debit transactions created")

        # ── Summary ───────────────────────────────────────────────────────────
        print("\nDone. Summary by month:")
        for month in all_months:
            end = next_month(month) - timedelta(days=1)
            from app.models.delivery import Delivery as D
            from sqlalchemy import func
            d_count = D.query.filter(D.delivery_date >= month, D.delivery_date <= end).count()
            t_credit = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.transaction_type == 'credit',
                Transaction.date >= month,
                Transaction.date <= end,
            ).scalar() or 0
            t_debit = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.transaction_type == 'debit',
                Transaction.date >= month,
                Transaction.date <= end,
            ).scalar() or 0
            label = "← past" if month < month_start(today) else ("← current" if month == month_start(today) else "→ future")
            print(f"  {month.strftime('%Y-%m')}  deliveries={d_count:3d}  "
                  f"revenue=₴{t_credit:,}  expenses=₴{t_debit:,}  "
                  f"profit=₴{t_credit - t_debit:,}  {label}")


if __name__ == '__main__':
    main()
