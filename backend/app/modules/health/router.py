"""Liveness and readiness probes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    """Returns OK if the process is up. Used by container liveness checks."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Returns OK only if dependencies (the database) are reachable."""
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
