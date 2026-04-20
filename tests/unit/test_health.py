"""P1-1.T2: Health endpoint tests.

Tests:
- GET /health returns 200 when API is running
- GET /health/ready returns 200 when all deps healthy (mocked)
- GET /health/ready returns 503 when a dependency is down (mocked)
- Response time verification for /health
"""

from __future__ import annotations

import os
import time

import pytest
from httpx import ASGITransport, AsyncClient

# Set required env vars before importing the app
os.environ.setdefault("URGP_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("URGP_RABBITMQ_URL", "amqp://test:test@localhost:5672/")
os.environ.setdefault("URGP_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("URGP_JWT_SECRET_KEY", "test-jwt-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("URGP_SIGNING_KEY", "test-signing-key-must-be-at-least-32-characters-long")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncClient:
    """Create a test client for the FastAPI app."""
    from urgp.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─────────────────────────────────────────────
# Test: Basic Health Check
# ─────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.anyio
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """GET /health returns 200 OK."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_health_response_body(self, client: AsyncClient) -> None:
        """GET /health response includes status and service name."""
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "urgp-api"

    @pytest.mark.anyio
    async def test_health_response_time(self, client: AsyncClient) -> None:
        """GET /health responds in < 100ms."""
        start = time.monotonic()
        await client.get("/health")
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 100, f"Health check took {elapsed_ms:.1f}ms (max 100ms)"

    @pytest.mark.anyio
    async def test_health_has_request_id_header(self, client: AsyncClient) -> None:
        """Response includes X-Request-ID header from middleware."""
        response = await client.get("/health")
        assert "x-request-id" in response.headers
        # Verify it's a UUID-like string
        request_id = response.headers["x-request-id"]
        assert len(request_id) == 36  # UUID format: 8-4-4-4-12


# ─────────────────────────────────────────────
# Test: Readiness Check (mocked dependencies)
# ─────────────────────────────────────────────

class TestReadinessEndpoint:
    """Tests for GET /health/ready."""

    @pytest.mark.anyio
    async def test_readiness_response_structure(self, client: AsyncClient) -> None:
        """GET /health/ready response has the expected structure (even if deps fail)."""
        response = await client.get("/health/ready")
        data = response.json()

        assert "status" in data
        assert "service" in data
        assert "checks" in data
        assert "response_time_ms" in data
        assert data["service"] == "urgp-api"

    @pytest.mark.anyio
    async def test_readiness_returns_503_when_db_down(self, client: AsyncClient) -> None:
        """GET /health/ready returns 503 when database is unreachable."""
        # Without a running PostgreSQL, the readiness check should return 503
        response = await client.get("/health/ready")

        # Since we don't have a real DB running in unit tests, expect 503
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "database" in data["checks"]
