"""Triage engine abstraction (ADR-0006).

A single provider-abstraction layer sits between business logic and the LLM so:
  * the model per task is a config value,
  * the provider can be swapped without touching the service layer, and
  * tests (and key-less local runs) use a deterministic stub.

The engine exposes `classify` and `draft_reply` separately so the service can
retrieve grounding context (RAG) between the two steps. `triage` is a
convenience that runs both with no context.

`ClaudeTriageEngine` uses tiered models — a cheap/fast model for classification
(structured output, validated server-side) and a strong model for reply drafting.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Protocol

from app.core.config import Settings, get_settings
from app.modules.triage.constants import CATEGORIES, CATEGORY_TO_TEAM, TEAMS
from app.modules.triage.prompts import (
    CLASSIFY_SYSTEM,
    DRAFT_SYSTEM,
    classify_user_prompt,
    draft_user_prompt,
    format_sources,
)
from app.modules.triage.schemas import (
    CLASSIFICATION_JSON_SCHEMA,
    TriageClassification,
    TriageResult,
)

if TYPE_CHECKING:
    from app.modules.retrieval.schemas import RetrievedDoc

logger = logging.getLogger(__name__)


def _sources_for_prompt(context: list[RetrievedDoc]) -> str:
    return format_sources([(d.title, d.snippet) for d in context])


class TriageEngine(Protocol):
    async def classify(self, subject: str, body: str) -> TriageClassification: ...
    async def draft_reply(
        self, subject: str, body: str, classification: TriageClassification,
        context: list[RetrievedDoc],
    ) -> str: ...
    async def triage(self, subject: str, body: str) -> TriageResult: ...


class ClaudeTriageEngine:
    """Real engine backed by the Anthropic Claude API."""

    def __init__(self, api_key: str, model_classify: str, model_draft: str) -> None:
        from anthropic import AsyncAnthropic

        from app.core.llm_observability import get_recorder

        self._client = AsyncAnthropic(api_key=api_key)
        self._model_classify = model_classify
        self._model_draft = model_draft
        self._recorder = get_recorder()  # Langfuse; no-op unless configured

    async def classify(self, subject: str, body: str) -> TriageClassification:
        resp = await self._client.messages.create(
            model=self._model_classify,
            max_tokens=512,
            system=CLASSIFY_SYSTEM,
            messages=[{"role": "user", "content": classify_user_prompt(subject, body)}],
            output_config={
                "format": {"type": "json_schema", "schema": CLASSIFICATION_JSON_SCHEMA}
            },
        )
        text = next(b.text for b in resp.content if b.type == "text")
        self._recorder.record_generation(
            name="triage.classify",
            model=self._model_classify,
            input=classify_user_prompt(subject, body),
            output=text,
            usage=resp.usage,
        )
        return TriageClassification.model_validate(json.loads(text))

    async def draft_reply(
        self, subject: str, body: str, classification: TriageClassification,
        context: list[RetrievedDoc],
    ) -> str:
        resp = await self._client.messages.create(
            model=self._model_draft,
            max_tokens=1024,
            system=DRAFT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": draft_user_prompt(
                        subject, body, classification.category, classification.priority,
                        _sources_for_prompt(context),
                    ),
                }
            ],
        )
        draft = "".join(b.text for b in resp.content if b.type == "text").strip()
        self._recorder.record_generation(
            name="triage.draft",
            model=self._model_draft,
            input=f"{subject}\n{body}",
            output=draft,
            usage=resp.usage,
        )
        return draft

    async def triage(self, subject: str, body: str) -> TriageResult:
        classification = await self.classify(subject, body)
        draft = await self.draft_reply(subject, body, classification, [])
        return TriageResult(classification=classification, draft_reply=draft)


class StubTriageEngine:
    """Deterministic, dependency-free engine for tests and key-less runs."""

    _KEYWORDS: list[tuple[tuple[str, ...], str]] = [
        (("refund", "charge", "invoice", "payment", "billing", "card"), "billing"),
        (("error", "bug", "crash", "broken", "500", "fails", "not working"), "technical_issue"),
        (("login", "password", "account", "sign in", "locked"), "account"),
        (("feature", "request", "would be nice", "suggestion", "add"), "feature_request"),
        (("angry", "terrible", "unacceptable", "worst", "complaint"), "complaint"),
    ]

    async def classify(self, subject: str, body: str) -> TriageClassification:
        text = f"{subject} {body}".lower()

        category = next(
            (cat for kws, cat in self._KEYWORDS if any(k in text for k in kws)),
            "general_inquiry",
        )
        if any(w in text for w in ("urgent", "asap", "immediately", "outage", "down")):
            priority = "urgent"
        elif category in ("technical_issue", "billing", "complaint"):
            priority = "high"
        elif category == "feature_request":
            priority = "low"
        else:
            priority = "medium"

        if any(w in text for w in ("angry", "terrible", "unacceptable", "worst", "frustrat")):
            sentiment = "negative"
        elif any(w in text for w in ("thanks", "great", "love", "appreciate")):
            sentiment = "positive"
        else:
            sentiment = "neutral"

        summary = (body.strip().split("\n", 1)[0])[:140] or subject
        return TriageClassification(
            category=category,
            priority=priority,
            sentiment=sentiment,
            assigned_team=CATEGORY_TO_TEAM.get(category, "general_support"),
            summary=summary,
        )

    async def draft_reply(
        self, subject: str, body: str, classification: TriageClassification,
        context: list[RetrievedDoc],
    ) -> str:
        grounding = " Based on related guidance [1]," if context else ""
        return (
            f"Hi,\n\nThanks for reaching out about \"{subject}\".{grounding} "
            "we've received your request and our team is looking into it. "
            "We'll follow up shortly with an update.\n\nBest regards,\nSupport Team"
        )

    async def triage(self, subject: str, body: str) -> TriageResult:
        classification = await self.classify(subject, body)
        draft = await self.draft_reply(subject, body, classification, [])
        return TriageResult(classification=classification, draft_reply=draft)


def normalize_classification(c: TriageClassification) -> TriageClassification:
    """Clamp model output to the controlled vocabularies (defensive)."""
    if c.category not in CATEGORIES:
        c.category = "general_inquiry"
    if c.assigned_team not in TEAMS:
        c.assigned_team = CATEGORY_TO_TEAM.get(c.category, "general_support")
    return c


def _normalize(result: TriageResult) -> TriageResult:
    normalize_classification(result.classification)
    return result


def get_triage_engine(settings: Settings | None = None) -> TriageEngine:
    """Return the configured engine: Claude when an API key is set, else the stub."""
    settings = settings or get_settings()
    if settings.anthropic_api_key:
        logger.info("Using ClaudeTriageEngine (classify=%s, draft=%s)",
                    settings.model_classify, settings.model_draft)
        return ClaudeTriageEngine(
            api_key=settings.anthropic_api_key,
            model_classify=settings.model_classify,
            model_draft=settings.model_draft,
        )
    logger.info("ANTHROPIC_API_KEY not set — using StubTriageEngine")
    return StubTriageEngine()
