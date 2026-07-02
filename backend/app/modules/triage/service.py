"""Triage service — classify, retrieve grounding context (RAG), draft a cited
reply, and persist the results (ADR-0002/0007).

In Phase 3 this is the unit the async worker calls off the request path; Phase 4
adds the retrieval step between classification and drafting.
"""

from __future__ import annotations

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.metrics import observe_triage
from app.core.telemetry import traced
from app.modules.retrieval.embeddings import EmbeddingProvider, get_embedder
from app.modules.retrieval.repository import (
    KnowledgeRepository,
    get_knowledge_repository,
)
from app.modules.retrieval.service import retrieve_context
from app.modules.tickets.models import (
    Ticket,
    TicketPriority,
    TicketSentiment,
    TicketStatus,
)
from app.modules.triage.engine import (
    TriageEngine,
    get_triage_engine,
    normalize_classification,
)
from app.modules.triage.schemas import Citation, TriageResult


async def triage_ticket(
    session: AsyncSession,
    ticket: Ticket,
    engine: TriageEngine | None = None,
    *,
    embedder: EmbeddingProvider | None = None,
    repo: KnowledgeRepository | None = None,
) -> TriageResult:
    """Classify, retrieve context, draft a cited reply, and persist results."""
    settings = get_settings()
    engine = engine or get_triage_engine()
    embedder = embedder or get_embedder()
    repo = repo or get_knowledge_repository(session)

    started = time.perf_counter()

    with traced("triage.classify"):
        classification = normalize_classification(
            await engine.classify(ticket.subject, ticket.body)
        )

    with traced("triage.retrieve"):
        docs = await retrieve_context(
            f"{ticket.subject}\n{ticket.body}",
            settings.rag_top_k,
            embedder=embedder,
            repo=repo,
        )
    needs_review = (not docs) or (docs[0].score < settings.rag_min_score)

    with traced("triage.draft"):
        draft = await engine.draft_reply(
            ticket.subject, ticket.body, classification, docs
        )

    citations = [
        Citation(
            ref=i,
            source_type=d.source_type,
            source_id=d.source_id,
            title=d.title,
            score=round(d.score, 4),
        )
        for i, d in enumerate(docs, start=1)
    ]

    ticket.category = classification.category
    ticket.priority = TicketPriority(classification.priority)
    ticket.sentiment = TicketSentiment(classification.sentiment)
    ticket.assigned_team = classification.assigned_team
    ticket.ai_summary = classification.summary
    ticket.ai_draft_reply = draft
    ticket.ai_citations = [c.model_dump() for c in citations]
    ticket.needs_review = needs_review

    if ticket.status == TicketStatus.NEW:
        ticket.status = TicketStatus.OPEN

    await session.commit()
    await session.refresh(ticket)

    observe_triage(
        classification.category, needs_review, time.perf_counter() - started
    )

    return TriageResult(
        classification=classification,
        draft_reply=draft,
        citations=citations,
        needs_review=needs_review,
    )
