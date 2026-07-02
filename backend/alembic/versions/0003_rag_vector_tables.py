"""RAG: pgvector tables + ticket citation/review columns

Revision ID: 0003_rag
Revises: 0002_ai_draft_reply
Create Date: 2026-06-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_rag"
down_revision: str | None = "0002_ai_draft_reply"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector extension was created in 0001.
    op.create_table(
        "kb_articles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX ix_kb_articles_embedding ON kb_articles "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "ticket_embeddings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ticket_embeddings_ticket_id", "ticket_embeddings", ["ticket_id"])
    op.execute(
        "CREATE INDEX ix_ticket_embeddings_embedding ON ticket_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.add_column(
        "tickets",
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "tickets", sa.Column("ai_citations", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tickets", "ai_citations")
    op.drop_column("tickets", "needs_review")
    op.drop_index("ix_ticket_embeddings_embedding", table_name="ticket_embeddings")
    op.drop_index("ix_ticket_embeddings_ticket_id", table_name="ticket_embeddings")
    op.drop_table("ticket_embeddings")
    op.drop_index("ix_kb_articles_embedding", table_name="kb_articles")
    op.drop_table("kb_articles")
