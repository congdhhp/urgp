"""Integration test fixtures — requires Docker Compose services.

Run with:
    docker compose up -d
    make migrate
    poetry run pytest tests/integration/ -v -m integration --timeout=60
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_KEY = os.getenv("URGP_API_KEYS_0", "dev-ingest-api-key-change-me")
USER_ID = "qa-tester@example.com"
MAILHOG_URL = os.getenv("MAILHOG_URL", "http://localhost:8025")

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create the FastAPI application with real service connections."""
    from urgp.main import create_app

    return create_app()


@pytest_asyncio.fixture
async def started_app(app):
    """Start the lifespan of the application (connects to DB, Redis, RabbitMQ)."""
    from urgp.main import lifespan

    async with lifespan(app):
        yield app


@pytest_asyncio.fixture
async def client(started_app) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the real FastAPI app via ASGI transport."""
    transport = ASGITransport(app=started_app)
    async with WorkerBackedAsyncClient(started_app, transport=transport, base_url="http://testserver") as ac:
        yield ac


class WorkerBackedAsyncClient(AsyncClient):
    """ASGI test client that processes accepted ingest payloads synchronously."""

    def __init__(self, app, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app = app

    async def post(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        response = await super().post(url, *args, **kwargs)
        if url == "/api/v1/ingest" and response.status_code == 202 and kwargs.get("json") is not None:
            await self._process_ingest(kwargs["json"])
        return response

    async def _process_ingest(self, payload_json: dict[str, Any]) -> None:
        from urgp.schemas.ingest import IngestPayload
        from urgp.services.build_processing import BuildEventProcessor
        from urgp.services.cache import CacheService
        from urgp.services.signature import ManifestSignatureService

        try:
            payload = IngestPayload.model_validate(payload_json)
        except ValidationError:
            return

        resources = self._app.state.resources
        processor = BuildEventProcessor(
            resources.require_session_factory,
            ManifestSignatureService(resources.settings.signing_key),
            resources.settings,
            cache=CacheService(
                redis_client_provider=lambda: resources.redis,
                default_ttl=resources.settings.redis_cache_ttl,
            ),
        )
        await processor.process(payload)


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


@pytest.fixture
def api_headers() -> dict[str, str]:
    """Pre-configured headers with API key and user ID."""
    return {
        "X-API-Key": API_KEY,
        "X-User-Id": USER_ID,
    }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clean_db(started_app):
    """Truncate all data tables after each test for isolation.

    Uses the session_factory from the running app to execute TRUNCATE CASCADE.
    """
    await _truncate_db(started_app)
    yield  # test runs here
    await _truncate_db(started_app)


@pytest_asyncio.fixture(autouse=True)
async def clean_redis(started_app):
    """Clear Redis-backed rate limit and idempotency keys between tests."""
    redis_client = getattr(started_app.state, "redis", None)
    if redis_client is not None:
        await redis_client.flushdb()
    yield
    if redis_client is not None:
        await redis_client.flushdb()


async def _truncate_db(started_app) -> None:
    """Remove relational test data while preserving the migrated schema."""

    session_factory = started_app.state.session_factory
    if session_factory is None:
        return

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                __import__("sqlalchemy").text(
                    "TRUNCATE TABLE "
                    "notifications, notification_subscriptions, "
                    "artifacts, build_commits, commit_prs, commit_issues, "
                    "pull_requests, issues, commits, "
                    "build_manifests, releases, products "
                    "CASCADE"
                )
            )


# ---------------------------------------------------------------------------
# MailHog helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mailhog_client() -> AsyncGenerator[AsyncClient, None]:
    """httpx client for MailHog REST API v2."""
    async with AsyncClient(base_url=MAILHOG_URL, timeout=5.0) as mc:
        yield mc


async def clear_mailhog(mailhog: AsyncClient) -> None:
    """Delete all messages from MailHog."""
    with suppress(httpx.HTTPError):
        await mailhog.delete("/api/v1/messages")


async def get_mailhog_messages(mailhog: AsyncClient) -> list[dict[str, Any]]:
    """Retrieve all messages from MailHog."""
    try:
        response = await mailhog.get("/api/v2/messages")
        if response.status_code == 200:
            return response.json().get("items", [])
    except httpx.HTTPError:
        pass
    return []


# ---------------------------------------------------------------------------
# Build event payload helpers
# ---------------------------------------------------------------------------


def make_ingest_payload(
    *,
    product_id: str = "e2e-test-product",
    release: str = "1.0.0-RC1",
    build_type: str = "nightly",
    build_id: str = "e2e-build-001",
    commit_hash: str | None = None,
    commit_repo: str = "github.com/test/repo",
    artifact_name: str = "test-artifact.zip",
    artifact_sha256: str | None = None,
) -> dict[str, Any]:
    """Create a valid ingest payload for E2E testing."""
    return {
        "product_id": product_id,
        "release": release,
        "build_type": build_type,
        "build_id": build_id,
        "cli_version": "0.1.0",
        "commit_hashes": [
            {
                "repository": commit_repo,
                "hash": commit_hash or "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "branch": "main",
            },
        ],
        "artifacts": [
            {
                "name": artifact_name,
                "type": "generic",
                "storage_uri": f"https://artifacts.example.com/{artifact_name}",
                "sha256": artifact_sha256 or ("ab" * 32),
                "size_bytes": 1048576,
                "metadata": {"test": True},
            },
        ],
        "timestamp": "2026-05-06T12:00:00Z",
        "ci_metadata": {
            "ci_system": "GitHub Actions",
            "pipeline_url": "https://github.com/test/repo/actions/runs/12345",
            "triggered_by": "e2e-test",
        },
    }


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


async def poll_build_status(
    client: AsyncClient,
    build_id: str,
    headers: dict[str, str],
    *,
    target_statuses: set[str] | None = None,
    timeout: float = 15.0,
    interval: float = 0.5,
) -> dict[str, Any] | None:
    """Poll GET /api/v1/builds/{build_id} until status matches or timeout."""
    if target_statuses is None:
        target_statuses = {"completed", "testing", "released"}

    elapsed = 0.0
    while elapsed < timeout:
        response = await client.get(f"/api/v1/builds/{build_id}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") in target_statuses:
                return data
        await asyncio.sleep(interval)
        elapsed += interval
    return None
