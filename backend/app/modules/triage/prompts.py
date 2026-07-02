"""Prompt templates for the triage pipeline.

Kept as plain constants/functions so they are easy to version and, in Phase 5,
to track in Langfuse.
"""

from app.modules.triage.constants import CATEGORIES, TEAMS

CLASSIFY_SYSTEM = (
    "You are a support-ticket triage assistant. Classify the ticket precisely. "
    f"Choose category from: {', '.join(CATEGORIES)}. "
    f"Choose assigned_team from: {', '.join(TEAMS)}. "
    "Set priority by urgency/impact (urgent = outage, data loss, or blocked "
    "payment; low = cosmetic or informational). Set sentiment from the "
    "customer's tone. Keep summary to one factual sentence."
)

DRAFT_SYSTEM = (
    "You are a helpful, empathetic customer-support agent. Write a concise, "
    "professional reply to the customer's ticket. Acknowledge their issue, give "
    "clear next steps, and do not invent facts, account details, or promises. "
    "If sources are provided, ground your reply in them and cite the ones you "
    "use inline as [1], [2], etc. If the sources do not help, do not invent "
    "facts — say what information you would need. Do not include a subject line; "
    "write only the reply body."
)


def classify_user_prompt(subject: str, body: str) -> str:
    return f"Ticket subject: {subject}\n\nTicket body:\n{body}"


def format_sources(sources: list[tuple[str, str]]) -> str:
    """Render (title, snippet) pairs as a numbered, citable sources block."""
    if not sources:
        return "(No relevant sources were found.)"
    return "\n\n".join(
        f"[{i}] {title}\n{snippet}" for i, (title, snippet) in enumerate(sources, start=1)
    )


def draft_user_prompt(
    subject: str, body: str, category: str, priority: str, sources_block: str
) -> str:
    return (
        f"Ticket subject: {subject}\n\n"
        f"Ticket body:\n{body}\n\n"
        f"(Internal context — category: {category}, priority: {priority}.)\n\n"
        f"Sources you may cite:\n{sources_block}\n\n"
        "Write the reply to the customer, citing sources inline as [n] where used."
    )
