"""Retrieval service — embed + search, KB ingestion, resolved-ticket indexing."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.retrieval.embeddings import EmbeddingProvider, get_embedder
from app.modules.retrieval.repository import (
    KnowledgeRepository,
    get_knowledge_repository,
)
from app.modules.retrieval.schemas import RetrievedDoc
from app.modules.tickets.models import Ticket


async def retrieve_context(
    query: str,
    k: int,
    *,
    embedder: EmbeddingProvider,
    repo: KnowledgeRepository,
) -> list[RetrievedDoc]:
    """Embed the query and return the top-k grounding documents."""
    vector = await embedder.embed(query)
    return await repo.search(vector, k)


async def add_kb_article(
    session: AsyncSession,
    title: str,
    content: str,
    *,
    embedder: EmbeddingProvider | None = None,
    repo: KnowledgeRepository | None = None,
) -> str:
    embedder = embedder or get_embedder()
    repo = repo or get_knowledge_repository(session)
    vector = await embedder.embed(f"{title}\n{content}")
    return await repo.add_kb_article(title, content, vector)


async def index_resolved_ticket(
    session: AsyncSession,
    ticket: Ticket,
    *,
    embedder: EmbeddingProvider | None = None,
    repo: KnowledgeRepository | None = None,
) -> None:
    """Embed a resolved ticket (subject + body + draft) for future retrieval."""
    embedder = embedder or get_embedder()
    repo = repo or get_knowledge_repository(session)
    text = f"{ticket.subject}\n{ticket.body}"
    if ticket.ai_draft_reply:
        text += f"\n\nResolution:\n{ticket.ai_draft_reply}"
    vector = await embedder.embed(text)
    await repo.index_ticket(str(ticket.id), ticket.subject, text, vector)
