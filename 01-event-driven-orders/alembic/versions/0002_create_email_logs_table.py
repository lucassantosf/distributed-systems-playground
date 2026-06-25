"""create email_logs table

Revision ID: 0002_create_email_logs_table
Revises: 0001_create_orders_table
Create Date: 2026-06-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_create_email_logs_table'
down_revision = '0001_create_orders_table'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('email_logs')
