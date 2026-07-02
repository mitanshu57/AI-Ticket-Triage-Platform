"""OpenTelemetry setup + a safe span helper (ADR-0008).

The module-level tracer uses OTel's default no-op provider until
`configure_telemetry` installs a real one — so `traced(...)` is safe to use
everywhere (including tests and key-less runs) and only emits spans when OTel is
enabled. Instrumentation is wrapped in try/except so a missing collector or
package never breaks the app.
"""

from __future__ import annotations

import logging

from opentelemetry import trace

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# No-op until a provider is configured.
tracer = trace.get_tracer("triage")


def traced(name: str, **attributes):
    """Start a span as the current context. No-op without a configured provider."""
    return tracer.start_as_current_span(name, attributes=attributes or None)


def configure_telemetry(service_name: str, app=None) -> None:
    """Install the OTLP tracer provider and auto-instrument libraries.

    `app` is the FastAPI app for the API process; pass None for the worker.
    """
    settings = get_settings()
    if not settings.otel_enabled:
        logger.info("OTEL disabled — telemetry not configured")
        return

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )
        trace.set_tracer_provider(provider)

        _instrument(app)
        logger.info("OpenTelemetry configured for service=%s", service_name)
    except Exception as exc:  # pragma: no cover - depends on optional infra
        logger.warning("OpenTelemetry setup failed: %s", exc)


def _safe(label: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # pragma: no cover - optional instrumentation
        logger.warning("instrumentation '%s' failed: %s", label, exc)


def _instrument(app) -> None:  # pragma: no cover - exercised only with OTEL on
    from app.core.database import engine

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _safe("fastapi", lambda: FastAPIInstrumentor.instrument_app(app))

    def _sqlalchemy():
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    def _redis():
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()

    def _httpx():
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

    def _asyncpg():
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()

    _safe("sqlalchemy", _sqlalchemy)
    _safe("redis", _redis)
    _safe("httpx", _httpx)
    _safe("asyncpg", _asyncpg)
