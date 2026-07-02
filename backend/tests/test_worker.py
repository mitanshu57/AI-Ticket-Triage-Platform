"""Worker job tests — run_triage exercised directly with a SQLite factory and a
fake publisher, so no Redis is required."""

import uuid

from app.modules.tickets.models import Ticket, TicketStatus
from app.worker import run_triage


async def _make_ticket(factory, **kwargs) -> uuid.UUID:
    defaults = dict(
        subject="Refund please",
        body="I was charged twice for my invoice, please refund.",
        requester_email="user@example.com",
        status=TicketStatus.NEW,
    )
    defaults.update(kwargs)
    async with factory() as s:
        ticket = Ticket(**defaults)
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)
        return ticket.id


async def test_run_triage_triages_and_publishes(db_factory):
    ticket_id = await _make_ticket(db_factory)

    published: list[uuid.UUID] = []

    async def fake_publish(ticket):
        published.append(ticket.id)

    await run_triage(
        {"session_factory": db_factory, "publish": fake_publish}, str(ticket_id)
    )

    async with db_factory() as s:
        ticket = await s.get(Ticket, ticket_id)
        assert ticket.category == "billing"
        assert ticket.status == TicketStatus.OPEN
        assert ticket.ai_draft_reply
    assert published == [ticket_id]


async def test_run_triage_unknown_ticket_is_noop(db_factory):
    published = []

    async def fake_publish(ticket):
        published.append(ticket.id)

    # Should not raise and should not publish.
    await run_triage(
        {"session_factory": db_factory, "publish": fake_publish}, str(uuid.uuid4())
    )
    assert published == []
