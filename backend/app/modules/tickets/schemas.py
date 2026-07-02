"""Pydantic request/response schemas for the tickets module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.tickets.models import (
    TicketPriority,
    TicketSentiment,
    TicketStatus,
)


class TicketCreate(BaseModel):
    """Payload to open a new ticket. Only customer-provided fields."""

    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    requester_email: EmailStr


class TicketUpdate(BaseModel):
    """Partial update. All fields optional; only provided fields change."""

    subject: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1)
    status: TicketStatus | None = None
    category: str | None = Field(default=None, max_length=100)
    priority: TicketPriority | None = None
    sentiment: TicketSentiment | None = None
    assigned_team: str | None = Field(default=None, max_length=100)
    ai_summary: str | None = None


class TicketRead(BaseModel):
    """Full ticket representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    body: str
    requester_email: str
    status: TicketStatus
    category: str | None
    priority: TicketPriority | None
    sentiment: TicketSentiment | None
    assigned_team: str | None
    ai_summary: str | None
    ai_draft_reply: str | None
    ai_citations: list | None
    needs_review: bool
    created_at: datetime
    updated_at: datetime


class TicketList(BaseModel):
    """Paginated list envelope."""

    items: list[TicketRead]
    total: int
    limit: int
    offset: int
