"""Test fixtures: an isolated in-memory SQLite DB and an httpx client.

Using SQLite keeps the suite dependency-free (no Postgres needed for unit
tests). Tables are created from the ORM metadata rather than Alembic, since the
Postgres-specific migration (pgvector, native enums) does not apply to SQLite.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_session
from app.main import app


@pytest.fixture(autouse=True)
def _reset_knowledge_base():
    """Clear the in-process knowledge repository between tests."""
    from app.modules.retrieval.repository import reset_in_memory_repository

    reset_in_memory_repository()
    yield
    reset_in_memory_repository()


@pytest_asyncio.fixture
async def db_factory():
    """An initialized in-memory SQLite session factory.

    For testing components that open their own sessions (the worker, dispatch),
    rather than receiving one via FastAPI's dependency.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    # A single shared in-memory connection for the test (StaticPool).
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:
    """An AsyncClient bound to the app, with the DB dependency overridden to
    use the test session."""

    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
