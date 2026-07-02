"""Observability tests — span helper is a safe no-op, /metrics is exposed and
records custom metrics, Langfuse is no-op without keys, trace propagation works."""

from httpx import AsyncClient

from app.core.llm_observability import LangfuseRecorder, get_recorder
from app.core.telemetry import traced

TICKET = {
    "subject": "Refund for double charge",
    "body": "I was charged twice for my invoice, please refund.",
    "requester_email": "user@example.com",
}


async def test_traced_is_noop_without_provider():
    # No OTel provider configured in tests -> using traced() must not raise.
    with traced("test.span", foo="bar") as span:
        assert span is not None  # no-op span object


async def test_metrics_endpoint_exposed(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Unlabeled counters are present immediately at 0.
    assert "triage_tickets_created_total" in body


async def test_metrics_record_create_and_triage(client: AsyncClient):
    created = (await client.post("/api/v1/tickets", json=TICKET)).json()
    await client.post(f"/api/v1/tickets/{created['id']}/triage")

    body = (await client.get("/metrics")).text
    assert "triage_tickets_created_total" in body
    # Labeled completion counter appears once a triage has run.
    assert "triage_completed_total" in body
    assert "triage_duration_seconds" in body


async def test_langfuse_recorder_is_noop_without_keys():
    recorder = get_recorder()
    assert isinstance(recorder, LangfuseRecorder)
    assert recorder.enabled is False
    # Must be a safe no-op.
    recorder.record_generation(
        name="x", model="m", input="i", output="o", usage=None
    )


async def test_trace_context_propagation_roundtrip():
    from opentelemetry.propagate import extract, inject

    carrier: dict = {}
    inject(carrier)  # no active span -> empty carrier, but callable
    ctx = extract(carrier)  # must return a usable context object
    assert ctx is not None
