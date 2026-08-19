"""fix_inventory_idempotency_unique_constraint

Altera a constraint de idempotência de UNIQUE(event_id) para
UNIQUE(event_id, product_id), permitindo que um evento com múltiplos
itens crie uma reserva por produto mantendo idempotência por pedido+produto.

Revision ID: i200bde221f1
Revises: i100acd110e0
Create Date: 2026-08-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'i200bde221f1'
down_revision: Union[str, None] = 'i100acd110e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove o índice único sobre apenas event_id
    op.drop_index('ix_inventory_reservations_event_id', table_name='inventory_reservations')

    # Recria como índice não-único (para lookups de idempotência por query)
    op.create_index('ix_inventory_reservations_event_id', 'inventory_reservations', ['event_id'], unique=False)

    # Cria constraint composta UNIQUE(event_id, product_id) — idempotência real por item
    op.create_index(
        'uq_inventory_reservations_event_product',
        'inventory_reservations',
        ['event_id', 'product_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_inventory_reservations_event_product', table_name='inventory_reservations')
    op.drop_index('ix_inventory_reservations_event_id', table_name='inventory_reservations')
    op.create_index('ix_inventory_reservations_event_id', 'inventory_reservations', ['event_id'], unique=True)
