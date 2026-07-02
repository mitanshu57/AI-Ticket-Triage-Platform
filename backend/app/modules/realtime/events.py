"""Serialize ticket changes and publish them to the realtime broker."""

from __future__ import annotations

import json

from app.modules.realtime.broker import Broker, get_broker
from app.modules.tickets.models import Ticket
from app.modules.tickets.schemas import TicketRead

# Single channel for all ticket events; clients filter by payload if needed.
TICKETS_CHANNEL = "tickets"


async def publish_ticket_event(
    ticket: Ticket,
    event: str = "ticket.triaged",
    broker: Broker | None = None,
) -> None:
    """Publish a ticket event (default: triage completed) to subscribers."""
    broker = broker or get_broker()
    payload = {
        "event": event,
        "ticket": TicketRead.model_validate(ticket).model_dump(mode="json"),
    }
    await broker.publish(TICKETS_CHANNEL, json.dumps(payload))
