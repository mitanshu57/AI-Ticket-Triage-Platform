"""Realtime tests — in-memory broker delivery and ticket-event serialization."""

import asyncio
import json

from app.modules.realtime.broker import InMemoryBroker
from app.modules.realtime.events import TICKETS_CHANNEL, publish_ticket_event
from app.modules.tickets.models import Ticket, TicketStatus


async def test_inmemory_broker_delivers_to_subscriber():
    broker = InMemoryBroker()
    received: list[str] = []

    async def consume():
        async for msg in broker.subscribe("c"):
            received.append(msg)
            break

    task = asyncio.create_task(consume())
    # Wait until the subscriber has registered its queue.
    for _ in range(100):
        await asyncio.sleep(0)
        if broker._subscribers.get("c"):
            break

    await broker.publish("c", "hello")
    await asyncio.wait_for(task, timeout=1)
    assert received == ["hello"]


async def test_inmemory_broker_publish_with_no_subscribers_is_noop():
    broker = InMemoryBroker()
    await broker.publish("c", "x")  # must not raise


async def test_publish_ticket_event_serializes(db_factory):
    # Create a ticket (committed → has timestamps for TicketRead validation).
    async with db_factory() as s:
        ticket = Ticket(
            subject="Refund",
            body="charged twice",
            requester_email="user@example.com",
            status=TicketStatus.OPEN,
            category="billing",
        )
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)

        recorded: list[tuple[str, str]] = []

        class RecordingBroker:
            async def publish(self, channel: str, message: str) -> None:
                recorded.append((channel, message))

            def subscribe(self, channel: str):  # pragma: no cover - unused
                raise NotImplementedError

        await publish_ticket_event(ticket, broker=RecordingBroker())

    assert len(recorded) == 1
    channel, raw = recorded[0]
    assert channel == TICKETS_CHANNEL
    payload = json.loads(raw)
    assert payload["event"] == "ticket.triaged"
    assert payload["ticket"]["category"] == "billing"
    assert payload["ticket"]["subject"] == "Refund"
