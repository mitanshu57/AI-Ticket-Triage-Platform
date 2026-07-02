"""RAG tests — hashing embedder, in-memory similarity search, and RAG-integrated
triage producing citations and the needs-review guardrail. All offline."""

from httpx import AsyncClient

from app.modules.retrieval.embeddings import EMBEDDING_DIM, HashingEmbedder
from app.modules.retrieval.repository import InMemoryKnowledgeRepository
from app.modules.retrieval.service import retrieve_context
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.triage.engine import StubTriageEngine
from app.modules.triage.service import triage_ticket


async def test_hashing_embedder_is_deterministic_and_normalized():
    emb = HashingEmbedder()
    v1 = await emb.embed("password reset help")
    v2 = await emb.embed("password reset help")
    assert v1 == v2
    assert len(v1) == EMBEDDING_DIM
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6


async def test_hashing_embedder_captures_similarity():
    emb = HashingEmbedder()
    q = await emb.embed("how do I reset my password")
    related = await emb.embed("steps to reset your account password")
    unrelated = await emb.embed("the invoice shows a duplicate charge")

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=False))

    assert cos(q, related) > cos(q, unrelated)


async def test_in_memory_search_ranks_relevant_first():
    emb = HashingEmbedder()
    repo = InMemoryKnowledgeRepository()
    await repo.add_kb_article(
        "Password reset",
        "To reset your password, use the reset link.",
        await emb.embed("reset password account login link"),
    )
    await repo.add_kb_article(
        "Refund policy",
        "Refunds are issued within 5 business days.",
        await emb.embed("refund billing invoice charge money"),
    )

    docs = await retrieve_context(
        "I forgot my password and cannot log in", k=2, embedder=emb, repo=repo
    )
    assert docs
    assert docs[0].title == "Password reset"
    assert docs[0].score > docs[1].score


async def test_triage_uses_rag_and_cites(db_factory):
    emb = HashingEmbedder()
    repo = InMemoryKnowledgeRepository()
    await repo.add_kb_article(
        "Handling duplicate charges",
        "If a customer is charged twice, verify the duplicate and issue a refund.",
        await emb.embed("duplicate charge refund billing invoice payment twice"),
    )

    async with db_factory() as session:
        ticket = Ticket(
            subject="Charged twice",
            body="I was charged twice for my invoice, please refund the duplicate payment.",
            requester_email="user@example.com",
            status=TicketStatus.NEW,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

        result = await triage_ticket(
            session, ticket, engine=StubTriageEngine(), embedder=emb, repo=repo
        )

    assert result.citations  # grounded in the KB article
    assert result.citations[0].source_type == "kb"
    assert result.needs_review is False
    assert "[1]" in result.draft_reply
    assert ticket.ai_citations  # persisted


async def test_triage_flags_needs_review_without_context(db_factory):
    emb = HashingEmbedder()
    repo = InMemoryKnowledgeRepository()  # empty

    async with db_factory() as session:
        ticket = Ticket(
            subject="Random question",
            body="Just wondering about something unrelated.",
            requester_email="user@example.com",
            status=TicketStatus.NEW,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

        result = await triage_ticket(
            session, ticket, engine=StubTriageEngine(), embedder=emb, repo=repo
        )

    assert result.citations == []
    assert result.needs_review is True


async def test_kb_endpoints(client: AsyncClient):
    resp = await client.post(
        "/api/v1/kb",
        json={"title": "Reset password", "content": "Use the password reset link in settings."},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Reset password"

    listing = await client.get("/api/v1/kb")
    assert listing.status_code == 200
    titles = [a["title"] for a in listing.json()]
    assert "Reset password" in titles
