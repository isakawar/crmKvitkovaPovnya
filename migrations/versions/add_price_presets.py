"""add price_presets table and simplify price rows to one_time/subscription

Revision ID: add_price_presets
Revises: add_size_sort_order
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_price_presets'
down_revision = 'add_size_sort_order'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create price_presets table
    op.create_table(
        'price_presets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 2. Insert default preset
    op.execute("""
        INSERT INTO price_presets (id, name, is_active, created_at)
        VALUES (1, 'Основний', true, NOW())
    """)

    # 3. Add new columns (nullable first for data migration)
    op.add_column('prices', sa.Column('preset_id', sa.Integer(), nullable=True))
    op.add_column('prices', sa.Column('order_type', sa.String(20), nullable=True))

    # 4. Migrate existing data
    op.execute("""
        UPDATE prices SET preset_id = 1, order_type = 'one_time'
        WHERE subscription_type_id IS NULL
    """)
    op.execute("""
        UPDATE prices SET preset_id = 1, order_type = 'subscription'
        WHERE subscription_type_id IS NOT NULL
    """)

    # 5. Remove duplicate subscription rows — keep one per size (they have the same price)
    op.execute("""
        DELETE FROM prices
        WHERE id NOT IN (
            SELECT MIN(id) FROM prices
            WHERE order_type = 'subscription'
            GROUP BY size_id
        )
        AND order_type = 'subscription'
    """)

    # 6. Make columns NOT NULL
    op.alter_column('prices', 'preset_id', nullable=False)
    op.alter_column('prices', 'order_type', nullable=False)

    # 7. Drop old unique constraint
    op.drop_constraint('uq_price_sub_size', 'prices', type_='unique')

    # 8. Add new unique constraint
    op.create_unique_constraint('uq_price_preset_type_size', 'prices', ['preset_id', 'order_type', 'size_id'])

    # 9. Add FK constraint for preset_id
    op.create_foreign_key(
        'fk_prices_preset_id', 'prices', 'price_presets',
        ['preset_id'], ['id'], ondelete='CASCADE'
    )

    # 10. Drop old column
    op.drop_column('prices', 'subscription_type_id')


def downgrade():
    op.add_column('prices', sa.Column('subscription_type_id', sa.Integer(), nullable=True))

    op.drop_constraint('fk_prices_preset_id', 'prices', type_='foreignkey')
    op.drop_constraint('uq_price_preset_type_size', 'prices', type_='unique')

    op.execute("""
        UPDATE prices SET subscription_type_id = NULL WHERE order_type = 'one_time'
    """)

    op.create_unique_constraint('uq_price_sub_size', 'prices', ['subscription_type_id', 'size_id'])

    op.drop_column('prices', 'order_type')
    op.drop_column('prices', 'preset_id')
    op.drop_table('price_presets')
