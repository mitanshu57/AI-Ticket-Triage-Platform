"""FastAPI application factory and lifespan (ADR-0003)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import configure_metrics
from app.core.telemetry import configure_telemetry
from app.modules.health.router import router as health_router
from app.modules.realtime.router import router as realtime_router
from app.modules.retrieval.router import router as kb_router
from app.modules.tickets.router import router as tickets_router
from app.modules.triage.router import router as triage_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    configure_telemetry(get_settings().otel_service_name, app=app)
    yield
    # Graceful shutdown hooks go here.


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AI Ticket Triage Platform",
        version="0.1.0",
        summary="Auto-classify, prioritize, route, and draft replies for support tickets.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(tickets_router)
    app.include_router(triage_router)
    app.include_router(kb_router)
    app.include_router(realtime_router)

    # Expose /metrics and instrument HTTP request metrics (ADR-0008).
    configure_metrics(app)

    @app.get("/", tags=["meta"], summary="Service banner")
    async def root() -> dict[str, str]:
        return {
            "service": "ai-ticket-triage",
            "version": app.version,
            "docs": "/docs",
        }

    return app


app = create_app()
