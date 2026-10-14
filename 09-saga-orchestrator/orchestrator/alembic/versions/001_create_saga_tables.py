"""create_sagas_steps_and_events_tables

Revision ID: 001_create_saga_tables
Revises: 
Create Date: 2026-10-13 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_create_saga_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enums nativos PostgreSQL
    saga_status_enum = postgresql.ENUM(
        'STARTED', 'RUNNING', 'COMPLETED', 'COMPENSATING', 'COMPENSATED', 'FAILED',
        name='saga_status_enum',
        create_type=False
    )
    saga_status_enum.create(op.get_bind(), checkfirst=True)

    step_status_enum = postgresql.ENUM(
        'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'COMPENSATING', 'COMPENSATED', 'COMPENSATING_FAILED',
        name='step_status_enum',
        create_type=False
    )
    step_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Tabela sagas
    op.create_table(
        'sagas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', sa.String(length=100), nullable=False),
        sa.Column('status', saga_status_enum, nullable=False, server_default='STARTED'),
        sa.Column('current_step_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_sagas_order_id', 'sagas', ['order_id'], unique=True)
    op.create_index('ix_sagas_status', 'sagas', ['status'])

    # 3. Tabela saga_steps
    op.create_table(
        'saga_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('saga_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sagas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_name', sa.String(length=100), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('status', step_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('command_id', sa.String(length=100), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_saga_steps_saga_id', 'saga_steps', ['saga_id'])
    op.create_index('ix_saga_steps_status', 'saga_steps', ['status'])
    op.create_index('ix_saga_steps_command_id', 'saga_steps', ['command_id'], unique=True)
    op.create_index('ix_saga_steps_saga_step_index', 'saga_steps', ['saga_id', 'step_index'], unique=True)

    # 4. Tabela saga_events (Audit Trail append-only)
    op.create_table(
        'saga_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('saga_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sagas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('saga_steps.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_saga_events_saga_id', 'saga_events', ['saga_id'])
    op.create_index('ix_saga_events_step_id', 'saga_events', ['step_id'])
    op.create_index('ix_saga_events_event_type', 'saga_events', ['event_type'])
    op.create_index('ix_saga_events_created_at', 'saga_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('saga_events')
    op.drop_table('saga_steps')
    op.drop_table('sagas')

    op.execute('DROP TYPE IF EXISTS step_status_enum')
    op.execute('DROP TYPE IF EXISTS saga_status_enum')

