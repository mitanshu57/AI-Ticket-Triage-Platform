"""Knowledge repository: similarity search over KB articles + resolved tickets.

`PgKnowledgeRepository` is the real pgvector implementation (Postgres only).
`InMemoryKnowledgeRepository` computes cosine in Python and is used in tests and
on any non-Postgres bind. `get_knowledge_repository(session)` picks based on the
session's dialect.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.retrieval.schemas import RetrievedDoc

_SNIPPET = 300


def _cosine(a: list[float], b: list[float]) -> float:
    # Vectors from the embedder are L2-normalized, so dot == cosine.
    return sum(x * y for x, y in zip(a, b, strict=False))


class KnowledgeRepository(Protocol):
    async def add_kb_article(self, title: str, content: str, embedding: list[float]) -> str: ...
    async def list_kb_articles(self) -> list[tuple[str, str]]: ...
    async def index_ticket(
        self, ticket_id: str, title: str, text: str, embedding: list[float]
    ) -> None: ...
    async def search(self, embedding: list[float], k: int) -> list[RetrievedDoc]: ...


class PgKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_kb_article(self, title: str, content: str, embedding: list[float]) -> str:
        from app.modules.retrieval.models import KBArticle

        article = KBArticle(title=title, content=content, embedding=embedding)
        self._session.add(article)
        await self._session.commit()
        await self._session.refresh(article)
        return str(article.id)

    async def list_kb_articles(self) -> list[tuple[str, str]]:
        from app.modules.retrieval.models import KBArticle

        rows = await self._session.scalars(
            select(KBArticle).order_by(KBArticle.created_at.desc())
        )
        return [(str(a.id), a.title) for a in rows]

    async def index_ticket(
        self, ticket_id: str, title: str, text: str, embedding: list[float]
    ) -> None:
        from app.modules.retrieval.models import TicketEmbedding

        self._session.add(
            TicketEmbedding(
                ticket_id=uuid.UUID(ticket_id), title=title, text=text, embedding=embedding
            )
        )
        await self._session.commit()

    async def search(self, embedding: list[float], k: int) -> list[RetrievedDoc]:
        from app.modules.retrieval.models import KBArticle, TicketEmbedding

        docs: list[RetrievedDoc] = []

        kb_dist = KBArticle.embedding.cosine_distance(embedding)
        for art, dist in (
            await self._session.execute(
                select(KBArticle, kb_dist.label("d")).order_by(kb_dist).limit(k)
            )
        ).all():
            docs.append(
                RetrievedDoc(
                    source_type="kb",
                    source_id=str(art.id),
                    title=art.title,
                    snippet=art.content[:_SNIPPET],
                    score=1.0 - float(dist),
                )
            )

        t_dist = TicketEmbedding.embedding.cosine_distance(embedding)
        for te, dist in (
            await self._session.execute(
                select(TicketEmbedding, t_dist.label("d")).order_by(t_dist).limit(k)
            )
        ).all():
            docs.append(
                RetrievedDoc(
                    source_type="ticket",
                    source_id=str(te.ticket_id),
                    title=te.title,
                    snippet=te.text[:_SNIPPET],
                    score=1.0 - float(dist),
                )
            )

        docs.sort(key=lambda d: d.score, reverse=True)
        return docs[:k]


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        # each entry: (source_type, source_id, title, text, embedding)
        self._items: list[tuple[str, str, str, str, list[float]]] = []

    def clear(self) -> None:
        self._items.clear()

    async def add_kb_article(self, title: str, content: str, embedding: list[float]) -> str:
        article_id = str(uuid.uuid4())
        self._items.append(("kb", article_id, title, content, embedding))
        return article_id

    async def list_kb_articles(self) -> list[tuple[str, str]]:
        return [(sid, title) for typ, sid, title, _t, _e in self._items if typ == "kb"]

    async def index_ticket(
        self, ticket_id: str, title: str, text: str, embedding: list[float]
    ) -> None:
        self._items.append(("ticket", ticket_id, title, text, embedding))

    async def search(self, embedding: list[float], k: int) -> list[RetrievedDoc]:
        scored = [
            RetrievedDoc(
                source_type=typ,
                source_id=sid,
                title=title,
                snippet=text[:_SNIPPET],
                score=_cosine(embedding, emb),
            )
            for typ, sid, title, text, emb in self._items
        ]
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:k]


_in_memory = InMemoryKnowledgeRepository()


def reset_in_memory_repository() -> None:
    """Clear the in-memory repository (used between tests)."""
    _in_memory.clear()


def _is_postgres(session: AsyncSession) -> bool:
    bind = session.bind
    return bind is not None and bind.dialect.name == "postgresql"


def get_knowledge_repository(session: AsyncSession) -> KnowledgeRepository:
    """Pg repo on Postgres binds; otherwise the process-wide in-memory repo."""
    if _is_postgres(session):
        return PgKnowledgeRepository(session)
    return _in_memory
