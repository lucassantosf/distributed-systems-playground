"""initial: create repositories and chunks tables

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Habilitar a extensão pgvector (precisa existir no PostgreSQL)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("github_url", sa.String(512), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        # Dimensão 1536 corresponde ao modelo text-embedding-3-small da OpenAI.
        # Se mudar o modelo, ajustar aqui e criar uma nova migration.
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Índice HNSW para busca por similaridade (mais rápido que IVFFlat para datasets menores)
    op.execute(
        "CREATE INDEX chunks_embedding_hnsw_idx ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Índice auxiliar para filtrar chunks por repositório antes da busca vetorial
    op.create_index("chunks_repository_id_idx", "chunks", ["repository_id"])


def downgrade() -> None:
    op.drop_index("chunks_repository_id_idx", table_name="chunks")
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw_idx")
    op.drop_table("chunks")
    op.drop_table("repositories")

