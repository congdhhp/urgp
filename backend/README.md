# URGP Backend

**FastAPI-based API server, async worker, and control-plane services for the Universal Release Governance Platform.**

## Components

| Component | Entry Point | Description |
|-----------|-------------|-------------|
| **API Server** | `urgp.main:app` | FastAPI REST API (ingest, builds, products, notifications, admin) |
| **Hydration Worker** | `urgp.worker.hydration_worker:run` | RabbitMQ consumer — traceability enrichment, notification delivery |

## Quick Start

```bash
cd backend
poetry install
```

### Run with Docker Compose (recommended)

```bash
# From repo root
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml exec urgp-api alembic upgrade head
```

### Run locally (requires Postgres, RabbitMQ, Redis)

```bash
cp .env.example .env   # Edit connection URLs
poetry run urgp-api     # Start API server
poetry run urgp-worker  # Start worker (separate terminal)
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/ingest` | API Key | Ingest build events |
| `GET` | `/api/v1/products` | API Key | List products |
| `GET` | `/api/v1/builds/{id}` | API Key | Get build details |
| `GET` | `/api/v1/builds/{id}/traceability` | API Key | Get traceability graph |
| `POST` | `/api/v1/notifications/subscriptions` | API Key | Subscribe to notifications |
| `GET` | `/health` | None | Health check |
| `GET` | `/readiness` | None | Readiness probe |
| `GET` | `/docs` | None | OpenAPI (Swagger) |

## Development

```bash
# Run unit tests
poetry run pytest tests/unit/ -v --cov=src/urgp

# Run integration tests (requires Docker services)
poetry run pytest tests/integration/ -v -m integration

# Lint & format
poetry run ruff check .
poetry run ruff format .

# Type check
poetry run mypy src/
```

## Database Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback last migration
poetry run alembic downgrade -1
```

## Project Structure

```text
backend/
├── src/urgp/
│   ├── api/             # Route handlers (products, builds, ingest, notifications, admin)
│   ├── db/              # Database session, seed data
│   ├── integrations/    # Git providers (GitHub, Bitbucket) and issue trackers (Jira)
│   ├── messaging/       # RabbitMQ publisher and topology
│   ├── middleware/       # API key auth, rate limiting, response headers, request ID
│   ├── models/          # SQLAlchemy ORM models and enums
│   ├── schemas/         # Pydantic request/response schemas
│   ├── services/        # Business logic (build processing, lifecycle, signatures, notifications)
│   ├── worker/          # Async message consumers (hydration, notifications)
│   ├── config.py        # Pydantic Settings (env vars with URGP_ prefix)
│   ├── dependencies.py  # FastAPI dependency injection
│   ├── logging.py       # Structured logging (structlog)
│   ├── main.py          # FastAPI app factory
│   └── runtime.py       # Application lifecycle management
├── tests/
│   ├── unit/            # 204 unit tests
│   └── integration/     # E2E pipeline, data accuracy, performance benchmarks
├── migrations/          # Alembic database migrations
├── config/              # Per-environment YAML configs (dev, staging, production)
├── .env.example         # Environment variable template
└── .env.docker          # Docker Compose environment
```
