"""Retrieval schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RetrievedDoc(BaseModel):
    """A document returned by similarity search."""

    source_type: str  # "kb" | "ticket"
    source_id: str
    title: str
    snippet: str
    score: float


class KBArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class KBArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime | None = None
