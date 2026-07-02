"""Langfuse LLM observability (ADR-0008).

A thin, no-op-safe recorder for per-call LLM traces (model, tokens, latency).
Active only when both Langfuse keys are configured and the `langfuse` package is
installed; otherwise every call is a no-op. This keeps LLM-cost/quality
visibility available without making Langfuse a hard dependency.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LangfuseRecorder:
    def __init__(self, client) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def record_generation(
        self, *, name: str, model: str, input: str, output: str, usage=None
    ) -> None:
        if self._client is None:
            return
        try:
            usage_details = None
            if usage is not None:
                usage_details = {
                    "input": getattr(usage, "input_tokens", None),
                    "output": getattr(usage, "output_tokens", None),
                }
            self._client.generation(
                name=name,
                model=model,
                input=input,
                output=output,
                usage_details=usage_details,
            )
        except Exception as exc:  # pragma: no cover - external service
            logger.warning("Langfuse record_generation failed: %s", exc)


_recorder: LangfuseRecorder | None = None


def get_recorder() -> LangfuseRecorder:
    global _recorder
    if _recorder is None:
        client = None
        settings = get_settings()
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Langfuse init failed: %s", exc)
                client = None
        _recorder = LangfuseRecorder(client)
    return _recorder
