"""Pub/sub broker abstraction for realtime fan-out (ADR-0008).

Two implementations behind one interface:

  * InMemoryBroker — asyncio queues, single process. Used when Redis is absent
    (single-process dev + tests). Publisher and subscriber must share the
    process, which holds because triage runs inline in the API process then.
  * RedisBroker — Redis pub/sub, multi-process. Bridges the separate ARQ worker
    process to API WebSocket clients when Redis is configured.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Protocol

from app.core.config import get_settings


class Broker(Protocol):
    async def publish(self, channel: str, message: str) -> None: ...
    def subscribe(self, channel: str) -> AsyncIterator[str]: ...


class InMemoryBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)

    async def publish(self, channel: str, message: str) -> None:
        for queue in list(self._subscribers.get(channel, ())):
            queue.put_nowait(message)

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers[channel].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[channel].discard(queue)


class RedisBroker:
    def __init__(self, redis) -> None:
        self._redis = redis

    async def publish(self, channel: str, message: str) -> None:
        await self._redis.publish(channel, message)

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") == "message":
                    data = msg["data"]
                    yield data.decode() if isinstance(data, bytes) else data
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


_broker: Broker | None = None


def get_broker() -> Broker:
    """Return the process-wide broker: Redis when configured, else in-memory."""
    global _broker
    if _broker is None:
        if get_settings().redis_url:
            from app.core.redis import get_redis

            _broker = RedisBroker(get_redis())
        else:
            _broker = InMemoryBroker()
    return _broker
