"""Vector-store ORM models (ADR-0004).

These live on a SEPARATE declarative base (`VectorBase`) from the core models so
that the pgvector `Vector` columns are never part of the metadata the test suite
creates on SQLite. They are created only by Alembic against Postgres.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.modules.retrieval.embeddings import EMBEDDING_DIM


class VectorBase(DeclarativeBase):
    """Declarative base for pgvector-backed tables (Postgres only)."""


class KBArticle(VectorBase):
    __tablename__ = "kb_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TicketEmbedding(VectorBase):
    """Embedding of a resolved ticket, indexed for retrieval as prior art."""

    __tablename__ = "ticket_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Decoupled from the tickets table (no DB FK) so the vector models stay on
    # their own metadata/lifecycle.
    ticket_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
