"""Prometheus metrics (ADR-0008).

Custom business + pipeline metrics live on the default registry and are exposed
at /metrics by `configure_metrics` (which also adds standard HTTP histograms via
prometheus-fastapi-instrumentator). The worker exposes the same custom metrics
on its own HTTP port via `start_worker_metrics_server`.
"""

from __future__ import annotations

import logging

from prometheus_client import Counter, Histogram

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TICKETS_CREATED = Counter(
    "triage_tickets_created_total", "Tickets created."
)
TRIAGE_ENQUEUED = Counter(
    "triage_jobs_enqueued_total", "Triage jobs handed to the worker."
)
TRIAGE_COMPLETED = Counter(
    "triage_completed_total",
    "Completed triage runs.",
    ["category", "needs_review"],
)
TRIAGE_DURATION = Histogram(
    "triage_duration_seconds", "End-to-end triage duration."
)


def inc_ticket_created() -> None:
    TICKETS_CREATED.inc()


def inc_triage_enqueued() -> None:
    TRIAGE_ENQUEUED.inc()


def observe_triage(category: str, needs_review: bool, seconds: float) -> None:
    TRIAGE_COMPLETED.labels(category=category, needs_review=str(needs_review).lower()).inc()
    TRIAGE_DURATION.observe(seconds)


_metrics_configured = False


def configure_metrics(app) -> None:
    """Expose /metrics and instrument HTTP request metrics (idempotent)."""
    global _metrics_configured
    if _metrics_configured or not get_settings().metrics_enabled:
        return
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    _metrics_configured = True


def start_worker_metrics_server() -> None:
    """Start a standalone metrics HTTP server for the worker process."""
    settings = get_settings()
    if not settings.metrics_enabled:
        return
    from prometheus_client import start_http_server

    start_http_server(settings.worker_metrics_port)
    logger.info("Worker metrics on :%s/metrics", settings.worker_metrics_port)
