"""Dispatch tests — enqueue path with a fake ARQ pool; no-op path without Redis."""

from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.triage import dispatch


async def test_enqueue_triage_enqueues_when_redis_configured(monkeypatch, db_factory):
    class FakeSettings:
        redis_url = "redis://fake:6379/0"

    jobs: list[tuple] = []

    class FakePool:
        async def enqueue_job(self, name, *args):
            jobs.append((name, args))

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr(dispatch, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(dispatch, "get_arq_pool", fake_get_pool)

    async with db_factory() as s:
        ticket = Ticket(
            subject="x", body="y", requester_email="a@b.com", status=TicketStatus.NEW
        )
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)

        enqueued = await dispatch.enqueue_triage(s, ticket)

        assert enqueued is True
        assert ticket.status == TicketStatus.TRIAGING
        # job is (name, (ticket_id, trace_carrier))
        assert len(jobs) == 1
        name, args = jobs[0]
        assert name == "run_triage"
        assert args[0] == str(ticket.id)
        assert isinstance(args[1], dict)


async def test_enqueue_triage_noop_without_redis(db_factory):
    # The test environment has no REDIS_URL, so real get_settings() -> None.
    async with db_factory() as s:
        ticket = Ticket(
            subject="x", body="y", requester_email="a@b.com", status=TicketStatus.NEW
        )
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)

        enqueued = await dispatch.enqueue_triage(s, ticket)

        assert enqueued is False
        assert ticket.status == TicketStatus.NEW
