"""Unit tests for the ingestion API endpoint (P1-3.T1, P1-3.T2, P1-3.T6).

Tests cover:
- P1-3.T1: Valid payload → HTTP 202 + message published
- P1-3.T2: Invalid payload → HTTP 422 + detailed validation errors
- P1-3.T6: Unauthenticated request → HTTP 401
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from urgp.main import create_app

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

_TEST_API_KEY = "test-api-key-for-gateway-tests"


def _valid_payload() -> dict:
    """Return a valid ingestion payload."""
    return {
        "product_id": "S32_IDE",
        "release": "3.6.8-RFP",
        "build_type": "nightly",
        "build_id": "260330",
        "cli_version": "1.0.0",
        "commit_hashes": [
            {
                "repository": "bitbucket.org/nxp/s32k3_dev",
                "hash": "a" * 40,
                "branch": "main",
            }
        ],
        "artifacts": [
            {
                "name": "s32-ide.zip",
                "type": "eclipse_p2",
                "storage_uri": "https://artifacts.internal/builds/260330/s32-ide.zip",
                "sha256": "a" * 64,
                "size_bytes": 1024000,
            }
        ],
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


def _create_mock_pipeline(current_count: int = 0) -> MagicMock:
    """Create a mock Redis pipeline (synchronous pipeline(), async execute())."""
    pipe = MagicMock()
    pipe.zremrangebyscore = MagicMock()
    pipe.zcard = MagicMock()
    pipe.zadd = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[0, current_count])
    return pipe


def _create_mock_redis() -> MagicMock:
    """Create a mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.pipeline.return_value = _create_mock_pipeline(0)
    return redis_mock


def _create_mock_publisher() -> AsyncMock:
    """Create a mock EventPublisher."""
    publisher = AsyncMock()
    publisher.publish = AsyncMock(return_value=datetime.now(tz=UTC))
    publisher.is_connected = True
    return publisher


def _create_mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock()
    settings.api_keys = [_TEST_API_KEY]
    settings.rate_limit_read = 100
    settings.rate_limit_write = 20
    return settings


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    mock_settings = _create_mock_settings()

    with patch("urgp.config.get_settings", return_value=mock_settings):
        app = create_app()
        app.state.redis = _create_mock_redis()
        app.state.publisher = _create_mock_publisher()
        yield TestClient(app), app.state.publisher


# ─────────────────────────────────────────────
# P1-3.T1: Valid Payload → HTTP 202
# ─────────────────────────────────────────────


class TestIngestValidPayload:
    """P1-3.T1: Valid payload → HTTP 202 + message in RabbitMQ."""

    def test_valid_payload_returns_202(self, client) -> None:
        """Valid payload is accepted with HTTP 202."""
        test_client, _ = client
        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["build_id"] == "260330"
        assert "ingestion_timestamp" in data
        assert data["message"] == "Build event accepted for processing"

    def test_valid_payload_publishes_to_rabbitmq(self, client) -> None:
        """Valid payload triggers a publish call."""
        test_client, mock_publisher = client
        test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": _TEST_API_KEY},
        )
        mock_publisher.publish.assert_called_once()

    def test_rate_limit_headers_present(self, client) -> None:
        """Rate limit headers are included in the response."""
        test_client, _ = client
        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


# ─────────────────────────────────────────────
# P1-3.T2: Invalid Payload → HTTP 422
# ─────────────────────────────────────────────


class TestIngestInvalidPayload:
    """P1-3.T2: Invalid payload → HTTP 422 + detailed validation errors."""

    def test_missing_required_field(self, client) -> None:
        """Missing required field returns 422."""
        test_client, _ = client
        payload = _valid_payload()
        del payload["build_id"]
        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_invalid_sha256_format(self, client) -> None:
        """Invalid SHA-256 format returns 422."""
        test_client, _ = client
        payload = _valid_payload()
        payload["artifacts"][0]["sha256"] = "not-a-valid-hash"
        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_invalid_build_type(self, client) -> None:
        """Invalid build_type enum returns 422."""
        test_client, _ = client
        payload = _valid_payload()
        payload["build_type"] = "invalid_type"
        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_empty_artifacts_list(self, client) -> None:
        """Empty artifacts list returns 422."""
        test_client, _ = client
        payload = _valid_payload()
        payload["artifacts"] = []
        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_empty_commit_hashes_list(self, client) -> None:
        """Empty commit_hashes list returns 422."""
        test_client, _ = client
        payload = _valid_payload()
        payload["commit_hashes"] = []
        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_duplicate_artifact_checksums(self, client) -> None:
        """Duplicate artifact checksums return 422."""
        test_client, _ = client
        payload = _valid_payload()
        payload["artifacts"].append(payload["artifacts"][0].copy())
        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_empty_body(self, client) -> None:
        """Empty request body returns 422."""
        test_client, _ = client
        response = test_client.post(
            "/api/v1/ingest",
            json={},
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 422


# ─────────────────────────────────────────────
# P1-3.T6: Unauthenticated → HTTP 401
# ─────────────────────────────────────────────


class TestIngestAuth:
    """P1-3.T6: Unauthenticated request → HTTP 401."""

    def test_missing_api_key_returns_401(self, client) -> None:
        """Request without X-API-Key header returns 401."""
        test_client, _ = client
        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
        )
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_invalid_api_key_returns_401(self, client) -> None:
        """Request with invalid API key returns 401."""
        test_client, _ = client
        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]
