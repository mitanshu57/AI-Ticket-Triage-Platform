"""Triage tests — exercised against the deterministic StubTriageEngine.

No API key is set in the test environment, so get_triage_engine() returns the
stub and the whole pipeline runs without network access.
"""

import pytest
from httpx import AsyncClient

from app.modules.triage.engine import StubTriageEngine, _normalize
from app.modules.triage.schemas import (
    CLASSIFICATION_JSON_SCHEMA,
    TriageClassification,
    TriageResult,
)

BILLING = {
    "subject": "Refund for double charge",
    "body": "I was charged twice for my invoice this month. Please refund the extra payment.",
    "requester_email": "user@example.com",
}
URGENT_BUG = {
    "subject": "Site is down",
    "body": "URGENT: the app crashes with a 500 error and is completely down for all users.",
    "requester_email": "user@example.com",
}


async def test_stub_classifies_billing():
    engine = StubTriageEngine()
    result = await engine.triage(BILLING["subject"], BILLING["body"])
    assert result.classification.category == "billing"
    assert result.classification.assigned_team == "billing"
    assert result.draft_reply


async def test_stub_detects_urgent_negative():
    engine = StubTriageEngine()
    result = await engine.triage(URGENT_BUG["subject"], URGENT_BUG["body"])
    assert result.classification.priority == "urgent"
    assert result.classification.category == "technical_issue"
    assert result.classification.assigned_team == "engineering"


async def test_triage_endpoint_populates_ticket(client: AsyncClient):
    created = (await client.post("/api/v1/tickets", json=BILLING)).json()
    assert created["category"] is None  # not yet triaged

    resp = await client.post(f"/api/v1/tickets/{created['id']}/triage")
    assert resp.status_code == 200
    data = resp.json()

    assert data["category"] == "billing"
    assert data["priority"] == "high"
    assert data["assigned_team"] == "billing"
    assert data["ai_summary"]
    assert data["ai_draft_reply"]
    # A freshly-created ticket advances out of NEW after triage.
    assert data["status"] == "open"


async def test_triage_missing_ticket_404(client: AsyncClient):
    resp = await client.post(
        "/api/v1/tickets/00000000-0000-0000-0000-000000000000/triage"
    )
    assert resp.status_code == 404


def test_normalize_clamps_unknown_values():
    bad = TriageResult(
        classification=TriageClassification(
            category="not_a_category",
            priority="high",
            sentiment="neutral",
            assigned_team="not_a_team",
            summary="x",
        ),
        draft_reply="hi",
    )
    fixed = _normalize(bad)
    assert fixed.classification.category == "general_inquiry"
    assert fixed.classification.assigned_team == "general_support"


def test_classification_schema_is_strict():
    # The JSON schema handed to the model must be strict-output compatible.
    assert CLASSIFICATION_JSON_SCHEMA["additionalProperties"] is False
    assert set(CLASSIFICATION_JSON_SCHEMA["required"]) == {
        "category",
        "priority",
        "sentiment",
        "assigned_team",
        "summary",
    }


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I love this product, thanks!", "positive"),
        ("This is terrible and unacceptable", "negative"),
        ("How do I export my data?", "neutral"),
    ],
)
async def test_stub_sentiment(text: str, expected: str):
    result = await StubTriageEngine().triage("subject", text)
    assert result.classification.sentiment == expected
