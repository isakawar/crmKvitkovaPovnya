"""One-time backfill: mark subscriptions as weddings based on the "для кого" field.

Managers historically flagged wedding subscriptions only by choosing
``for_whom = 'весільна підписка'``. This script promotes such subscriptions to
proper weddings (``is_wedding = True``) so they show up in the wedding analytics.

Matches: non-draft subscriptions whose ``for_whom`` equals «весільна підписка»
(case-insensitive, trimmed) and are not already flagged.

Usage (inside Docker):
    # Dry run — lists what would change, no writes:
    docker compose exec web python scripts/backfill_wedding_from_for_whom.py

    # Apply:
    docker compose exec web python scripts/backfill_wedding_from_for_whom.py --apply
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app import create_app
from app.extensions import db
from app.models.subscription import Subscription

TARGET_FOR_WHOM = 'весільна підписка'

app = create_app()
apply = '--apply' in sys.argv

with app.app_context():
    subs = (
        Subscription.query
        .filter(
            Subscription.status != 'draft',
            Subscription.is_wedding.is_(False),
            func.lower(func.trim(Subscription.for_whom)) == TARGET_FOR_WHOM,
        )
        .order_by(Subscription.id)
        .all()
    )

    print('=' * 60)
    print('BACKFILL WEDDING FROM for_whom', '(APPLIED)' if apply else '(DRY RUN)')
    print('=' * 60)
    print(f'  Знайдено підписок до оновлення: {len(subs)}')
    print()
    for s in subs:
        client = s.client
        label = (client.name or client.instagram or f'#{client.id}') if client else '—'
        print(f'  #{s.id:<6} {s.status:<10} {s.type or "?":<10} {label}')

    already = (
        Subscription.query
        .filter(Subscription.is_wedding.is_(True))
        .count()
    )
    print()
    print(f'  Весільних зараз (усього): {already}')

    if not subs:
        print('\n  Нічого оновлювати.')
        sys.exit(0)

    if not apply:
        print('\n  Це dry run. Запусти з --apply щоб застосувати.')
        sys.exit(0)

    from app.services.activity_log_service import log as _log
    for s in subs:
        s.is_wedding = True
        _log(None, 'update', 'subscription', s.id,
             f'Позначено весільною (backfill з поля «для кого») підписку #{s.id}')
    db.session.commit()

    print(f'\n  ✅ Оновлено {len(subs)} підписок. Весільних тепер: {already + len(subs)}')
