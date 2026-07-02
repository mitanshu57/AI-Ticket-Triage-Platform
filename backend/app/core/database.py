"""Async SQLAlchemy engine, session factory, and FastAPI dependency (ADR-0003/0004)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_settings = get_settings()

# `future`/2.0 style engine. echo off; SQL is observed via tracing in Phase 5.
engine = create_async_engine(_settings.database_url, pool_pre_ping=True)

SessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session and ensure it is closed."""
    async with SessionLocal() as session:
        yield session
