"""
Проставляє статус 'Доставлено' всім доставкам за квітень 2026,
які зараз мають статус 'Очікує' або 'Розподілено'.

Запуск в Docker:
    docker exec -it <container_name> python scripts/mark_april_delivered.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import date

from app import create_app
from app.extensions import db
from app.models.delivery import Delivery

YEAR = 2026
MONTH = 4
DATE_FROM = date(YEAR, MONTH, 1)
DATE_TO = date(YEAR, MONTH, 30)
PENDING_STATUSES = ('Очікує', 'Розподілено')


def main():
    app = create_app()
    with app.app_context():
        deliveries = (
            Delivery.query
            .filter(
                Delivery.delivery_date >= DATE_FROM,
                Delivery.delivery_date <= DATE_TO,
                Delivery.status.in_(PENDING_STATUSES),
            )
            .order_by(Delivery.delivery_date.asc())
            .all()
        )

        if not deliveries:
            print("Доставок для оновлення не знайдено.")
            return

        print(f"\n{'─'*60}")
        print(f"  Знайдено {len(deliveries)} доставок (квітень {YEAR})")
        print(f"{'─'*60}")
        print(f"  {'ID':>5}  {'Дата':<12}  {'Статус':<14}  Клієнт")
        print(f"{'─'*60}")
        for d in deliveries:
            client = d.client
            name = (client.instagram or client.phone or f'#{client.id}') if client else '—'
            print(f"  {d.id:>5}  {d.delivery_date}  {d.status:<14}  {name.lstrip('@')}")
        print(f"{'─'*60}\n")

        answer = input("Проставити всім статус 'Доставлено'? [yes/no]: ").strip().lower()
        if answer != 'yes':
            print("Скасовано.")
            return

        from app.services.delivery_service import set_delivery_status

        ok = 0
        errors = []
        for d in deliveries:
            try:
                set_delivery_status(d, 'Доставлено')
                ok += 1
                print(f"  ✓ #{d.id} ({d.delivery_date})")
            except Exception as e:
                db.session.rollback()
                errors.append((d.id, str(e)))
                print(f"  ✗ #{d.id} — {e}")

        print(f"\nГотово: {ok} оновлено, {len(errors)} помилок.")
        if errors:
            print("Помилки:")
            for eid, emsg in errors:
                print(f"  #{eid}: {emsg}")


if __name__ == '__main__':
    main()
