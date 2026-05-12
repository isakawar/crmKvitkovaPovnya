"""One-time script to backfill delivery_charge transactions for all past completed deliveries.

Usage (inside Docker container):
    # Dry run first — shows totals without making changes:
    docker compose exec web python scripts/reconcile_delivery_charges.py

    # Apply changes:
    docker compose exec web python scripts/reconcile_delivery_charges.py --apply
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.billing_service import reconcile_historical_charges

app = create_app()

dry_run = '--apply' not in sys.argv

with app.app_context():
    result = reconcile_historical_charges(dry_run=dry_run)

    print()
    print('=' * 50)
    print('RECONCILE DELIVERY CHARGES', '(DRY RUN)' if dry_run else '(APPLIED)')
    print('=' * 50)
    print(f"  Всього доставлених доставок:  {result['total_completed_deliveries']}")
    print(f"  Вже списано раніше:           {result['already_charged']}")
    print(f"  До обробки:                   {result['to_process']}")
    print(f"  Оброблено:                    {result['processed']}")
    print(f"  Пропущено (немає ціни):       {result['skipped_no_price']}")
    print(f"  Загальна сума списань:        {result['total_amount']} грн")
    print()

    if dry_run:
        print('Це dry run. Щоб застосувати зміни, запусти з --apply')
    else:
        print('Зміни збережено в БД.')
    print()
