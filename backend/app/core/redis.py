"""Lazy Redis + ARQ connection accessors (ADR-0005).

Only used when `REDIS_URL` is configured. Connections are created on first use
and cached for the process lifetime.
"""

from __future__ import annotations

from app.core.config import get_settings

_redis = None  # redis.asyncio.Redis — for pub/sub
_arq_pool = None  # arq.ArqRedis — for enqueueing jobs


def _require_url() -> str:
    url = get_settings().redis_url
    if not url:
        raise RuntimeError("REDIS_URL is not configured")
    return url


def get_redis():
    """Return a cached redis.asyncio client (used by the Redis broker)."""
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(_require_url())
    return _redis


async def get_arq_pool():
    """Return a cached ARQ pool for enqueueing jobs."""
    global _arq_pool
    if _arq_pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings

        _arq_pool = await create_pool(RedisSettings.from_dsn(_require_url()))
    return _arq_pool
