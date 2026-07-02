"""add ai_draft_reply column to tickets

Revision ID: 0002_ai_draft_reply
Revises: 0001_initial
Create Date: 2026-06-29

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_ai_draft_reply"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("ai_draft_reply", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "ai_draft_reply")
