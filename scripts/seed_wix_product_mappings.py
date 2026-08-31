"""Seed / update Wix product mappings.

Run once after deploy:

    flask db upgrade            # make sure wix_product_mapping table exists
    python scripts/seed_wix_product_mappings.py

Idempotent: matches by catalog_item_id, updates existing rows, inserts missing
ones, and leaves everything else untouched. Safe to re-run.

Notes
-----
* Cosmetics (crumb / LIPSS) are intentionally NOT mapped here: WixProductMapping
  requires a bouquet `size`, which does not apply to them. Such leads still show
  up in "Заявки з сайту" and are processed manually.
* Subscription rows leave `delivery_type` empty on purpose — the customer picks
  the cadence on the Wix site (it arrives in a separate payload field), so the
  manager confirms Weekly / Monthly / Bi-weekly on the order form.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.wix_product_mapping import WixProductMapping

# catalog_item_id, wix_item_name, order_scenario, delivery_type, size
MAPPINGS = [
    # --- Разова доставка ---
    ('b48ed03a-8e87-a0f5-652d-6372032bfce5', 'Разова доставка, розмір XXL', 'order', None, 'XXL'),
    ('b9e9ecac-82e4-a352-140c-bfc09b7a52ed', 'Разова доставка, розмір XL',  'order', None, 'XL'),
    ('6c1affe8-3076-efd5-e0ff-97f31c7aa016', 'Разова доставка, розмір L',   'order', None, 'L'),
    ('e9865e0a-e1a3-4a3c-53cc-260eeb55a39b', 'Разова доставка, розмір М',   'order', None, 'M'),
    # --- Підписка на квіти (4 доставки) ---
    ('a886d2e4-5e96-e4b5-c3c8-88e87092b4f6', 'Підписка на квіти XXL (4 доставки)', 'subscription', None, 'XXL'),
    ('ad657242-217e-9caf-7adb-7195f2e3cd5d', 'Підписка на квіти XL (4 доставки)',  'subscription', None, 'XL'),
    ('f6d51f47-5b4a-040c-8525-dfe813f8e2cf', 'Підписка на квіти L (4 доставки)',   'subscription', None, 'L'),
    ('977be4c1-a0f7-756d-7540-cf98f9208833', 'Підписка на квіти М (4 доставки)',   'subscription', None, 'M'),
    ('cb03817f-b63c-9ff2-25da-1a76db27c858', 'Підписка на квіти (власний бюджет)', 'subscription', None, 'Власний'),
]

# Products that arrive as leads but are not mapped (no bouquet size).
SKIPPED = [
    ('9150a9ac-cd52-d206-38b5-3e4f1dd50ac5', 'crumb (крем для рук 50 мл)'),
    ('9b2673ac-e566-d530-4a63-1dd93c208233', 'LIPSS (блиск для губ)'),
]


def main():
    app = create_app()
    with app.app_context():
        created, updated = 0, 0
        for catalog_item_id, name, scenario, delivery_type, size in MAPPINGS:
            row = WixProductMapping.query.filter_by(catalog_item_id=catalog_item_id).first()
            if row is None:
                row = WixProductMapping(catalog_item_id=catalog_item_id)
                db.session.add(row)
                created += 1
                action = 'CREATE'
            else:
                updated += 1
                action = 'UPDATE'
            row.wix_item_name = name
            row.order_scenario = scenario
            row.delivery_type = delivery_type
            row.size = size
            row.is_active = True
            print(f'{action:6} {catalog_item_id}  {scenario:12} {size:8} {name}')

        db.session.commit()

        print(f'\nDone: {created} created, {updated} updated.')
        print('Skipped (not mapped, handled manually):')
        for cid, label in SKIPPED:
            print(f'  {cid}  {label}')


if __name__ == '__main__':
    main()
