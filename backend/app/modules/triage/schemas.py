"""Triage result schemas + the JSON Schema used to constrain the classifier."""

from pydantic import BaseModel, ConfigDict

from app.modules.tickets.models import TicketPriority, TicketSentiment
from app.modules.triage.constants import (
    CATEGORIES,
    PRIORITY_VALUES,
    SENTIMENT_VALUES,
    TEAMS,
)


class TriageClassification(BaseModel):
    """Structured classification of a ticket."""

    model_config = ConfigDict(use_enum_values=True)

    category: str
    priority: TicketPriority
    sentiment: TicketSentiment
    assigned_team: str
    summary: str


class Citation(BaseModel):
    """A source the drafted reply was grounded in (ADR-0007)."""

    ref: int
    source_type: str
    source_id: str
    title: str
    score: float


class TriageResult(BaseModel):
    """Full triage output: classification + a (possibly cited) reply draft."""

    classification: TriageClassification
    draft_reply: str
    citations: list[Citation] = []
    # True when retrieval confidence was low — the draft should be reviewed by a
    # human before sending rather than presented as confident (ADR-0007).
    needs_review: bool = False


# JSON Schema handed to the Messages API `output_config.format` so the model's
# classification is validated server-side (ADR-0006). Built from the controlled
# vocabularies above to avoid drift.
CLASSIFICATION_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": PRIORITY_VALUES},
        "sentiment": {"type": "string", "enum": SENTIMENT_VALUES},
        "assigned_team": {"type": "string", "enum": TEAMS},
        "summary": {
            "type": "string",
            "description": "One-sentence summary of the ticket.",
        },
    },
    "required": ["category", "priority", "sentiment", "assigned_team", "summary"],
    "additionalProperties": False,
}
