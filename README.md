# AI News Intelligence Platform

An event-driven, real-time news intelligence system: ingest articles from many
sources, cluster them into stories, summarize with AI, and let users ask
questions with sourced answers (RAG).

This repo is being built incrementally, in phases — each phase produces a
working system before the next layer of complexity is added.

**Status: Phase 1 (MVP ingestion) — complete and verified.**

## Phase 1 — what's here

- FastAPI backend that polls a fixed list of RSS feeds on a schedule
  (APScheduler, every 10 min) and writes normalized articles to Postgres.
- Basic data validation (skip entries missing title/link) and duplicate
  prevention (`url` UNIQUE constraint).
- Fetches with retry + exponential backoff against flaky/slow feeds.
- REST API (`GET /api/articles`) to list ingested articles, with search and
  pagination.
- Next.js frontend that lists articles from the API.
- Everything runs via Docker Compose: `postgres`, `api`, `web`.

### What Phase 1 deliberately does NOT have yet

No Kafka, no clustering, no AI, no dedup beyond exact-URL matching. That's
intentional — see phases below.

## Running it

```bash
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:3000
- Postgres: localhost:5432 (`news_user` / `news_pass` / `news_intel`)

Ingestion runs automatically every 10 minutes. To trigger it immediately:

```bash
curl -X POST http://localhost:8000/api/ingest/run
```

## Architecture (target — most of this doesn't exist yet)

```
News Sources (RSS/APIs)
      ↓
Ingestion Layer
      ↓
Kafka (news.raw → news.normalized → news.processed → news.embeddings → news.story-updates → news.alerts)
      ↓
Processing Workers (clean → normalize → dedupe → extract entities → classify → embed → cluster)
      ↓
PostgreSQL (relational) + pgvector (semantic search) + Redis (cache) + S3 (raw storage)
      ↓
RAG Layer (question → embed → vector search → rerank → LLM → grounded answer + sources)
      ↓
FastAPI backend → React/Next.js frontend (WebSockets for live updates)
```

## Roadmap

| Phase | What it adds |
|---|---|
| 1 ✅ | MVP ingestion: RSS → Postgres → React |
| 2 | Kafka: producers, consumers, partitions, consumer groups |
| 3 | Article processing: cleaning, entity extraction, topic classification |
| 4 | Deduplication: title similarity, then semantic (embeddings) |
| 5 | Story clustering — the core of the project |
| 6 | AI summarization (what happened / why it matters / what's new) |
| 7 | Story timelines |
| 8 | RAG (question answering with source attribution) |
| 9 | Real-time updates via WebSockets |
| 10 | Personalized alerts |
| 11 | Redis caching |
| 12 | Reliability: retries, DLQs, idempotency, consumer failover |

Full design decisions, database schema, Kafka topic design, and load-testing
results will be documented here as each phase lands.

## Tech stack rationale

Every technology solves a specific problem — nothing is added for its own sake:

- **Kafka** — asynchronous event processing, decoupling ingestion from processing
- **PostgreSQL** — transactional relational data (users, articles, stories, relationships)
- **pgvector** — semantic retrieval for RAG and clustering
- **Redis** — caching hot stories/searches, rate limiting
- **S3** — raw article/document storage
- **WebSockets** — pushing real-time story updates to the browser
- **LLM** — summarization, classification, reasoning, RAG answers
- **Spark** (later) — high-volume stream processing once the workload justifies it

Kubernetes and Terraform are intentionally deferred until the core system
works and there's a concrete reason to reach for them.
