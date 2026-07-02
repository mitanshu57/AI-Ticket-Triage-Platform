"""Decide whether triage runs async (Redis/ARQ) or inline (ADR-0005).

`enqueue_triage` returns True if the job was handed to the worker (and the
ticket moved to TRIAGING), or False if no queue is configured — in which case
the caller runs triage inline. This keeps the API fast and resilient to LLM
latency when a worker is available, while still working in a single process.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.metrics import inc_triage_enqueued
from app.core.redis import get_arq_pool
from app.modules.tickets.models import Ticket, TicketStatus

logger = logging.getLogger(__name__)

# Must match the function name registered in app.worker.WorkerSettings.
TRIAGE_JOB = "run_triage"


async def enqueue_triage(session: AsyncSession, ticket: Ticket) -> bool:
    """Enqueue triage if a queue is configured. Returns True if enqueued."""
    if not get_settings().redis_url:
        return False

    ticket.status = TicketStatus.TRIAGING
    await session.commit()
    await session.refresh(ticket)

    # Propagate the current trace context to the worker for end-to-end traces
    # (ADR-0008). Empty carrier when OTel is not configured.
    from opentelemetry.propagate import inject

    carrier: dict = {}
    inject(carrier)

    pool = await get_arq_pool()
    await pool.enqueue_job(TRIAGE_JOB, str(ticket.id), carrier)
    inc_triage_enqueued()
    logger.info("Enqueued triage for ticket %s", ticket.id)
    return True
