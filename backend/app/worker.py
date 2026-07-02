"""ARQ worker entrypoint (ADR-0005).

Run with: `arq app.worker.WorkerSettings`

The worker consumes triage jobs, runs the (already-tested) triage service, and
publishes a realtime event so connected WebSocket clients update live. The job
function takes its session factory and publish hook from `ctx`, defaulting to
the app's real ones — which makes it directly unit-testable with a SQLite
factory and a fake publisher, no Redis required.
"""

from __future__ import annotations

import logging
import uuid

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.telemetry import tracer
from app.modules.realtime.events import publish_ticket_event
from app.modules.tickets import service as ticket_service
from app.modules.triage import service as triage_service

logger = logging.getLogger(__name__)


async def run_triage(ctx: dict, ticket_id: str, carrier: dict | None = None) -> None:
    """Triage one ticket and publish the result.

    `carrier` carries the enqueuing request's trace context so the worker span
    links to the API span (end-to-end distributed trace, ADR-0008).
    """
    from opentelemetry.propagate import extract

    parent = extract(carrier or {})
    session_factory = ctx.get("session_factory", SessionLocal)
    publish = ctx.get("publish", publish_ticket_event)

    with tracer.start_as_current_span("worker.run_triage", context=parent):
        async with session_factory() as session:
            ticket = await ticket_service.get_ticket(session, uuid.UUID(ticket_id))
            if ticket is None:
                logger.warning("Triage job for unknown ticket %s — skipping", ticket_id)
                return
            await triage_service.triage_ticket(session, ticket)
            await publish(ticket)
            logger.info(
                "Triaged ticket %s -> %s/%s", ticket_id, ticket.category, ticket.priority
            )


def _redis_settings():
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(get_settings().redis_url or "redis://localhost:6379")


async def _on_startup(ctx: dict) -> None:
    """Configure worker telemetry + expose worker metrics (ADR-0008)."""
    from app.core.logging import configure_logging
    from app.core.metrics import start_worker_metrics_server
    from app.core.telemetry import configure_telemetry

    configure_logging()
    configure_telemetry("triage-worker", app=None)
    start_worker_metrics_server()


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [run_triage]
    redis_settings = _redis_settings()
    on_startup = _on_startup
    max_jobs = 10
