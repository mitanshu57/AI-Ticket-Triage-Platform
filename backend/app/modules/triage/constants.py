"""Controlled vocabularies for triage.

Categories and teams are constrained to known sets so classification output is
predictable and routing is deterministic. Priority/sentiment reuse the ticket
domain enums (single source of truth).
"""

from app.modules.tickets.models import TicketPriority, TicketSentiment

# Ticket categories the classifier may choose from.
CATEGORIES: list[str] = [
    "billing",
    "technical_issue",
    "account",
    "feature_request",
    "general_inquiry",
    "complaint",
]

# Teams a ticket may be routed to.
TEAMS: list[str] = [
    "billing",
    "engineering",
    "customer_success",
    "general_support",
]

# Default routing from category -> team (used by the stub engine and as a
# fallback if the model returns an unknown team).
CATEGORY_TO_TEAM: dict[str, str] = {
    "billing": "billing",
    "technical_issue": "engineering",
    "account": "customer_success",
    "feature_request": "engineering",
    "general_inquiry": "general_support",
    "complaint": "customer_success",
}

PRIORITY_VALUES: list[str] = [p.value for p in TicketPriority]
SENTIMENT_VALUES: list[str] = [s.value for s in TicketSentiment]
