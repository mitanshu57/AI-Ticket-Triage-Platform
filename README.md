# AI Ticket Triage Platform

A full-stack platform that auto-classifies, prioritizes, routes, and drafts
replies for support tickets using LLMs + RAG — instrumented end-to-end for
observability.

> **Architecture decisions** are documented in [`docs/adr/`](docs/adr/).

## Tech stack (Phase 1)

- **Backend:** FastAPI (async), SQLAlchemy 2.0 (async) + asyncpg, Pydantic v2
- **Database:** PostgreSQL 16 with the `pgvector` extension (enabled now, used in Phase 4)
- **Migrations:** Alembic
- **Tests:** pytest + pytest-asyncio + httpx
- **Runtime:** Docker Compose

## Quick start

```bash
cp .env.example .env          # adjust if you like; defaults work
docker compose up --build     # brings up Postgres + API
```

Then open:

- API:        http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc:      http://localhost:8000/redoc
- Health:     http://localhost:8000/health

Migrations run automatically on container start (`alembic upgrade head`).

## Local development (without Docker for the API)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# point at the Dockerized Postgres (or your own)
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/triage
alembic upgrade head
uvicorn app.main:app --reload
```

## Running tests

```bash
cd backend
pip install -e ".[dev]"
pytest
```

Tests run against an isolated SQLite database by default, so no Postgres is
required to run the suite.

## Project layout

```
.
├── docker-compose.yml
├── .env.example
├── docs/adr/                 # Architecture Decision Records
└── backend/
    ├── Dockerfile
    ├── pyproject.toml
    ├── alembic.ini
    ├── alembic/              # migrations
    └── app/
        ├── main.py           # FastAPI app factory + lifespan
        ├── core/             # config, database, logging (cross-cutting)
        └── modules/          # bounded contexts (modular monolith, ADR-0002)
            ├── health/       # liveness/readiness
            └── tickets/      # ticket CRUD: models, schemas, service, router
```

## API (Phase 1)

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/health`            | Liveness probe |
| GET    | `/health/ready`      | Readiness probe (checks DB) |
| POST   | `/api/v1/tickets`    | Create a ticket |
| GET    | `/api/v1/tickets`    | List tickets (filter by status/category, paginated) |
| GET    | `/api/v1/tickets/{id}` | Get one ticket |
| PATCH  | `/api/v1/tickets/{id}` | Update a ticket |
| DELETE | `/api/v1/tickets/{id}` | Delete a ticket |
| POST   | `/api/v1/tickets/{id}/triage` | Run AI triage (async if a worker is up) |
| WS     | `/ws/tickets`        | Live stream of ticket events |

## AI triage (Phase 2)

`POST /api/v1/tickets/{id}/triage` runs the triage pipeline and fills in
`category`, `priority`, `sentiment`, `assigned_team`, `ai_summary`, and
`ai_draft_reply`, advancing the ticket from `new` to `open`.

- **Tiered models (ADR-0006):** `claude-haiku-4-5` for classification (cheap,
  high-volume, validated via structured output) and `claude-opus-4-8` for reply
  drafting (strong reasoning).
- **Provider abstraction:** all LLM access goes through `TriageEngine`, so the
  model per task is config and the provider is swappable/mockable.
- **Runs without a key:** if `ANTHROPIC_API_KEY` is unset, a deterministic
  `StubTriageEngine` is used — so the pipeline (and the test suite) runs with no
  network or credentials. Set the key in `.env` to use real Claude.

## Async processing + realtime (Phase 3)

Triage now runs off the request path (ADR-0005) and results stream live (ADR-0008):

- **Queue (ARQ + Redis):** when `REDIS_URL` is set, creating a ticket enqueues a
  triage job and the ticket moves to `triaging`; the **worker** (`arq
  app.worker.WorkerSettings`, a separate process) runs the triage service and
  publishes the result. The API never blocks on the LLM.
- **WebSocket:** clients connect to `ws://localhost:8000/ws/tickets` and receive
  `ticket.triaged` events as they complete.
- **Broker abstraction:** Redis pub/sub bridges worker → API across processes;
  with no Redis, an in-process broker is used and triage runs inline — so the
  whole flow (and the test suite) works in a single process with no Redis.

Behavior by configuration:

| `REDIS_URL` | Create a ticket | `POST /{id}/triage` | Realtime |
|-------------|-----------------|---------------------|----------|
| set | enqueues async (→ `triaging`) | `202`, worker triages | Redis pub/sub |
| unset | stays `new` | `200`, triages inline | in-process broker |

`docker compose up` runs Postgres, Redis, the API, and the worker together.

## RAG / cited replies (Phase 4)

Triage now retrieves grounding context before drafting (ADR-0004/0007):

1. **Index:** KB articles (`POST /api/v1/kb`) and resolved tickets (on
   transition to `resolved`) are embedded and stored in pgvector.
2. **Retrieve:** a new ticket is embedded and the top-k similar KB
   articles/tickets are fetched by cosine similarity.
3. **Generate:** the draft cites its sources inline as `[n]`; `ai_citations`
   records what was used.
4. **Guardrail:** if the best match scores below `RAG_MIN_SCORE`, the ticket is
   flagged `needs_review` instead of being presented as confident.

Pluggable, offline-friendly building blocks:

- **Embeddings** go through an `EmbeddingProvider`. Default `HashingEmbedder` is
  deterministic and dependency-free (Anthropic has no embeddings API); set
  `EMBEDDING_PROVIDER=voyage` + `VOYAGE_API_KEY` to use Voyage AI.
- **Vector store** is behind a `KnowledgeRepository`: `PgKnowledgeRepository`
  (pgvector, HNSW cosine index) on Postgres, `InMemoryKnowledgeRepository`
  (Python cosine) elsewhere — so RAG and the test suite run with no Postgres.

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/api/v1/kb` | Add a KB article (embedded + indexed) |
| GET    | `/api/v1/kb` | List KB articles |

## Observability (Phase 5)

End-to-end visibility across the stack (ADR-0008):

- **Distributed tracing (OpenTelemetry → Collector → Jaeger):** FastAPI,
  SQLAlchemy, Redis, and HTTP clients are auto-instrumented; custom spans wrap
  each triage stage (`triage.classify` → `triage.retrieve` → `triage.draft`).
  The enqueuing request's **trace context is propagated to the worker**, so a
  ticket's API request and its async triage appear in one trace.
- **Metrics (Prometheus + Grafana):** `/metrics` exposes standard HTTP
  histograms plus business/pipeline metrics — tickets created, jobs enqueued,
  triage completions by category, `needs_review` rate, and triage duration
  (p50/p95). The worker exposes the same on `:9100`. A provisioned Grafana
  dashboard ("AI Ticket Triage") renders them.
- **LLM observability (Langfuse, optional):** each Claude call records model +
  token usage. No-op unless `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are set
  (install with `pip install -e ".[langfuse]"`).

Everything is **safe-by-default**: spans use OTel's no-op tracer until
`OTEL_ENABLED=true`, and `/metrics` works with no collector — so the app and the
test suite run with zero observability infra.

UIs after `docker compose up`: Grafana → http://localhost:3001, Prometheus →
http://localhost:9090, Jaeger → http://localhost:16686.

## Frontend (Phase 6)

A **Next.js 14 (App Router) + TypeScript** dashboard (`frontend/`): submit
tickets, view AI classification + cited draft replies + `needs_review` flags,
and watch triage land **live** over the WebSocket. Types mirror the API
(`lib/types.ts`); `lib/useTicketStream.ts` is the reconnecting WS hook.

```bash
cd frontend && npm install && npm run dev     # http://localhost:3000
```

## LLM evaluation pipeline (Phase 6, ADR-0010)

Offline, quantified model-quality measurement — rare in portfolio projects:

```bash
cd backend && python -m app.eval.run          # accuracy, P/R/F1, confusion
```

- A version-controlled labeled dataset (`app/eval/dataset.json`).
- Per-field classification reports (category + priority): accuracy, per-label
  precision/recall/F1, macro-F1, confusion matrix.
- **Deterministic with the stub engine** (so it runs in CI without a key);
  measures the real model when `ANTHROPIC_API_KEY` is set.

## CI

`.github/workflows/ci.yml` runs on every push/PR: backend lint (ruff) + tests +
eval pipeline, frontend typecheck + build, and Docker image builds for both.

## Full stack

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend (dashboard) | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/docs |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
| Jaeger (traces) | http://localhost:16686 |
