"""Референційна цілісність: унікальності й узгоджена поведінка FK при видаленні.

Що лагодиться
-------------
1. `settings` — універсальний довідник (розміри, типи витрат, рахунки оплати) без
   унікальності. Два однакові розміри створювались без проблем, а
   `Settings.query.filter_by(type='size', value=...).first()` у get_order_price
   мовчки брав перший-ліпший — тобто ціна могла поїхати від дубля в довіднику.

2. `route_deliveries` без UNIQUE(route_id, delivery_id) — одна доставка могла
   потрапити у два маршрути одночасно.

3. `prices.size_id` мав ON DELETE CASCADE на `settings`: видалення розміру в
   Налаштуваннях тихо зносило прайси по всіх пресетах. Для довідника, на який
   посилаються гроші, правильна поведінка — RESTRICT (заборонити видалення), а
   не мовчазне знесення.

4. `order_photos.order_id` і `certificates.order_id` — FK без ON DELETE, через що
   видалення замовлення з фото/сертифікатом падало на IntegrityError. Сервіс це
   вже чистить явно; тут — захист на рівні БД на випадок інших шляхів.

Безпека застосування
--------------------
Пункти 1 і 2 можуть впасти на реальних даних, якщо там уже є дублі. Замість
криптичного constraint violation міграція спершу сама шукає дублі: у
`route_deliveries` вони — чисте сміття, тож чистяться автоматично (лишається
рядок із найменшим id); у `settings` автоматично чистити НЕ можна, бо на рядки
посилаються prices і transaction, тож міграція зупиняється з явним переліком.

Revision ID: add_referential_integrity_constraints
Revises: add_billing_performance_indexes
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_referential_integrity'
down_revision = 'add_billing_performance_indexes'
branch_labels = None
depends_on = None


def _fk_name(bind, table, column):
    """Знайти фактичне ім'я FK-констрейнта (частина створена без явних імен)."""
    return bind.execute(sa.text("""
        SELECT tc.constraint_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
         WHERE tc.constraint_type = 'FOREIGN KEY'
           AND tc.table_name = :table
           AND kcu.column_name = :column
         LIMIT 1
    """), {'table': table, 'column': column}).scalar()


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        # Тести піднімають схему через create_all на SQLite — міграції там не йдуть.
        return

    # ── 1. settings: UNIQUE(type, value) ──────────────────────────────────────
    duplicates = bind.execute(sa.text("""
        SELECT type, value, count(*) AS n
          FROM settings
         GROUP BY type, value
        HAVING count(*) > 1
         ORDER BY n DESC
    """)).fetchall()
    if duplicates:
        listing = '\n'.join(f'    {r.type} / {r.value!r} × {r.n}' for r in duplicates)
        raise RuntimeError(
            'У таблиці settings є дублікати, а на її рядки посилаються prices і\n'
            'transaction — автоматично злити їх не можна, бо невідомо, який рядок\n'
            'вважати основним. Приберіть дублі вручну (перепривʼязавши посилання),\n'
            f'потім повторіть міграцію:\n{listing}'
        )
    op.create_unique_constraint('uq_settings_type_value', 'settings', ['type', 'value'])

    # ── 2. route_deliveries: UNIQUE(route_id, delivery_id) ────────────────────
    # Дублі тут — чисте сміття (одна доставка двічі в одному маршруті),
    # лишаємо рядок із найменшим id.
    op.execute("""
        DELETE FROM route_deliveries rd
         WHERE rd.id > (
               SELECT min(rd2.id) FROM route_deliveries rd2
                WHERE rd2.route_id = rd.route_id
                  AND rd2.delivery_id = rd.delivery_id
         )
    """)
    op.create_unique_constraint(
        'uq_route_delivery_pair', 'route_deliveries', ['route_id', 'delivery_id']
    )

    # ── 3. prices.size_id: CASCADE → RESTRICT ─────────────────────────────────
    name = _fk_name(bind, 'prices', 'size_id')
    if name:
        op.drop_constraint(name, 'prices', type_='foreignkey')
    op.create_foreign_key(
        'fk_prices_size_id', 'prices', 'settings', ['size_id'], ['id'], ondelete='RESTRICT'
    )

    # ── 4. order_photos / certificates: явна поведінка при видаленні ──────────
    name = _fk_name(bind, 'order_photos', 'order_id')
    if name:
        op.drop_constraint(name, 'order_photos', type_='foreignkey')
    op.create_foreign_key(
        'fk_order_photos_order_id', 'order_photos', 'order', ['order_id'], ['id'],
        ondelete='CASCADE',
    )

    name = _fk_name(bind, 'certificates', 'order_id')
    if name:
        op.drop_constraint(name, 'certificates', type_='foreignkey')
    op.create_foreign_key(
        'fk_certificates_order_id', 'certificates', 'order', ['order_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    op.drop_constraint('fk_certificates_order_id', 'certificates', type_='foreignkey')
    op.create_foreign_key(
        'fk_certificates_order_id', 'certificates', 'order', ['order_id'], ['id']
    )

    op.drop_constraint('fk_order_photos_order_id', 'order_photos', type_='foreignkey')
    op.create_foreign_key(
        'order_photos_order_id_fkey', 'order_photos', 'order', ['order_id'], ['id']
    )

    op.drop_constraint('fk_prices_size_id', 'prices', type_='foreignkey')
    op.create_foreign_key(
        'prices_size_id_fkey', 'prices', 'settings', ['size_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('uq_route_delivery_pair', 'route_deliveries', type_='unique')
    op.drop_constraint('uq_settings_type_value', 'settings', type_='unique')
