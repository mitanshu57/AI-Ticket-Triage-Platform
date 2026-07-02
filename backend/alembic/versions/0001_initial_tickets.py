"""initial tickets table + pgvector extension

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ticket_status = postgresql.ENUM(
    "new", "triaging", "open", "pending", "resolved", "closed",
    name="ticket_status",
)
ticket_priority = postgresql.ENUM(
    "low", "medium", "high", "urgent", name="ticket_priority"
)
ticket_sentiment = postgresql.ENUM(
    "positive", "neutral", "negative", name="ticket_sentiment"
)


def upgrade() -> None:
    bind = op.get_bind()

    # Enable pgvector now; used by the RAG module in Phase 4 (ADR-0004/0007).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    ticket_status.create(bind, checkfirst=True)
    ticket_priority.create(bind, checkfirst=True)
    ticket_sentiment.create(bind, checkfirst=True)

    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("requester_email", sa.String(length=320), nullable=False),
        sa.Column(
            "status",
            ticket_status,
            nullable=False,
            server_default="new",
        ),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("priority", ticket_priority, nullable=True),
        sa.Column("sentiment", ticket_sentiment, nullable=True),
        sa.Column("assigned_team", sa.String(length=100), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_category", "tickets", ["category"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_index("ix_tickets_category", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_table("tickets")

    bind = op.get_bind()
    ticket_sentiment.drop(bind, checkfirst=True)
    ticket_priority.drop(bind, checkfirst=True)
    ticket_status.drop(bind, checkfirst=True)
