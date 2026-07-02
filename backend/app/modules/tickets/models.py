"""Ticket ORM model and enums (ADR-0002 tickets module).

AI-populated fields (category, priority, sentiment, assigned_team, ai_summary)
exist now but stay NULL until the triage pipeline lands in Phase 2+.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _pg_enum(py_enum: type[enum.Enum], name: str) -> Enum:
    """Build a SQLAlchemy Enum that stores the member *values* (lowercase),
    not the default member names — so the DB, API JSON, and migrations agree.
    """
    return Enum(
        py_enum,
        name=name,
        values_callable=lambda obj: [member.value for member in obj],
    )


class TicketStatus(str, enum.Enum):
    NEW = "new"
    TRIAGING = "triaging"
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketSentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Customer-provided fields ---
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    requester_email: Mapped[str] = mapped_column(String(320), nullable=False)

    # --- Workflow state ---
    status: Mapped[TicketStatus] = mapped_column(
        _pg_enum(TicketStatus, "ticket_status"),
        default=TicketStatus.NEW,
        nullable=False,
    )

    # --- AI-populated fields (NULL until Phase 2 triage) ---
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[TicketPriority | None] = mapped_column(
        _pg_enum(TicketPriority, "ticket_priority"), nullable=True
    )
    sentiment: Mapped[TicketSentiment | None] = mapped_column(
        _pg_enum(TicketSentiment, "ticket_sentiment"), nullable=True
    )
    assigned_team: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_draft_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sources the draft was grounded in (list of citation dicts) and a flag set
    # when retrieval confidence was low (ADR-0007).
    ai_citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
