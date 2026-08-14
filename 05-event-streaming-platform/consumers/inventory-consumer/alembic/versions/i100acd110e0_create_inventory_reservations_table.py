"""create_inventory_reservations_table

Revision ID: i100acd110e0
Revises: 
Create Date: 2026-08-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i100acd110e0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('inventory_reservations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_id', sa.String(length=36), nullable=False),
        sa.Column('event_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=255), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('quantity_reserved', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='RESERVED'),
        sa.Column('reserved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_reservations_event_id'), 'inventory_reservations', ['event_id'], unique=True)
    op.create_index(op.f('ix_inventory_reservations_order_id'), 'inventory_reservations', ['order_id'], unique=False)
    op.create_index(op.f('ix_inventory_reservations_product_id'), 'inventory_reservations', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_reservations_product_id'), table_name='inventory_reservations')
    op.drop_index(op.f('ix_inventory_reservations_order_id'), table_name='inventory_reservations')
    op.drop_index(op.f('ix_inventory_reservations_event_id'), table_name='inventory_reservations')
    op.drop_table('inventory_reservations')
