# Real-Time Analytics Platform

A mini event-analytics platform (think a small Mixpanel / Google Analytics) that ingests
events asynchronously and shows live metrics on a real-time dashboard. Built to explore
production-style backend architecture: async ingestion with a queue and workers, a proper
relational data model, WebSocket streaming, and full containerization.

**Live demo:** https://realtime-analytics-platform.onrender.com

> The demo runs on a free tier that sleeps after inactivity — the first load may take
> 30–60 seconds to wake up. It also runs a built-in **traffic simulator** so the dashboard
> always shows live data (see [Demo mode](#demo-mode)).

<!--
  GIF: graba un clip corto del dashboard con datos entrando (números subiendo, gráfico
  moviéndose) con ScreenToGif, súbelo al repo (por ejemplo en docs/dashboard.gif) y
  reemplaza la línea de abajo por:  ![Dashboard](docs/dashboard.gif)
-->
![Live dashboard demo](docs/Analytics.gif)

---

## Architecture

Events are accepted fast and processed in the background, so ingestion never blocks on the
database. The API only enqueues; workers do the writing.

```
Client ──POST /events──▶  API (FastAPI)  ──lpush──▶  Queue (Redis)
                                                        │
                                                        ▼ brpop
                                              Worker (background process)
                                                        │
                                                        ▼ commit
                                              Database (PostgreSQL)
                                                        │
                          Dashboard  ◀──WebSocket──  Metrics (aggregated queries)
```

- **Ingestion is decoupled from processing.** `POST /events` pushes to a Redis queue and
  returns `202 Accepted` immediately; a separate worker consumes the queue and persists to
  PostgreSQL. This keeps the API responsive under load and lets the pipeline scale by adding
  more workers.
- **Live metrics over WebSocket.** The dashboard opens a WebSocket and receives updated
  metrics (total events, unique users, events by type) every few seconds — no polling,
  no page reloads.

---

## Tech stack

| Layer            | Technology                                  |
|------------------|---------------------------------------------|
| API              | Python · FastAPI · Pydantic                 |
| Async / queue    | Redis (FIFO queue) · background worker       |
| Database         | PostgreSQL · SQLAlchemy (ORM) · Alembic      |
| Real-time        | WebSockets                                   |
| Dashboard        | Vanilla HTML / CSS / JS (no frameworks)      |
| Infra            | Docker · docker-compose                      |
| Deployment       | Render (managed PostgreSQL + Redis)          |

---

## Key design decisions

A few choices worth calling out (and why):

- **Queue + workers for ingestion.** The API accepts events and returns `202` without
  touching the database; the actual write happens in a worker. Recording an event should be
  cheap and fast even during traffic spikes.
- **Synchronous SQLAlchemy on purpose.** The workers (and the DB-facing HTTP endpoints) run
  synchronously so they never block the async event loop; the WebSocket handler bridges to
  the sync queries with `asyncio.to_thread`.
- **`JSONB` for event properties.** Fixed fields (`event_name`, `user_id`, `timestamp`) are
  indexed columns, while flexible per-event data lives in a `JSONB` column — structured where
  it matters, flexible where it helps.
- **Code-first schema with migrations.** The schema lives in code and in Git, reproducible
  anywhere with `alembic upgrade head` (run automatically on container startup).
- **Config via environment variables.** Secrets stay in `.env` (git-ignored) and are injected
  per environment — never baked into the image.

---

## Running it locally

The whole system (API, worker, PostgreSQL, Redis) runs with a single command.

**Requirements:** Docker and Docker Compose.

```bash
# 1. Clone the repo
git clone https://github.com/Alejandro-Tuz/realtime-analytics-platform.git
cd realtime-analytics-platform

# 2. Create a .env file (see .env.example) with your DATABASE_URL and REDIS_URL

# 3. Start everything
docker compose up --build
```

Then open:

- Dashboard: http://localhost:8000/static/index.html
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

Migrations run automatically on startup, so the database schema is created for you.

### Sending a test event

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"event_name": "page_view", "user_id": "u1", "properties": {"page": "/home"}}'
```

The API responds with `202 Accepted`; the worker picks the event up and stores it, and the
dashboard updates in real time.

---

## API endpoints

| Method | Path                | Description                                  |
|--------|---------------------|----------------------------------------------|
| POST   | `/events`           | Ingest an event (enqueues, returns `202`)    |
| GET    | `/metrics/summary`  | Aggregated metrics (total, unique users, by type) |
| WS     | `/ws/metrics`       | Live metrics stream for the dashboard         |
| GET    | `/health`           | Health check                                  |

---

## Demo mode

The production demo doesn't have real users, so it includes a lightweight **event traffic
simulator** that generates realistic random events (page views, clicks, purchases, etc.)
to keep the live dashboard populated. It's enabled only in the deployed environment via a
`DEMO_MODE=true` environment variable and is disabled during local development. This is a
presentation aid for the demo — not real user traffic.

---

## What I learned

Building this end to end meant working through real backend problems: decoupling ingestion
with a queue, bridging synchronous database code with an asynchronous WebSocket handler,
containerizing a multi-service app, handling a race condition in the migration step, and
deploying to a managed cloud environment. Every decision above is one I can explain and
defend.
