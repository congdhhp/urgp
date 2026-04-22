"""Unit tests for the ingestion API endpoint (P1-3)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.unit.fakes import FakeRedis
from urgp.config import get_settings
from urgp.main import create_app
from urgp.services.idempotency import IdempotencyService

_TEST_API_KEY = "test-api-key-for-gateway-tests"


def _valid_payload(*, build_id: str = "260330") -> dict[str, object]:
    return {
        "product_id": "S32_IDE",
        "release": "3.6.8-RFP",
        "build_type": "nightly",
        "build_id": build_id,
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


def _create_mock_settings(**overrides: object) -> MagicMock:
    settings = MagicMock()
    settings.api_keys = [_TEST_API_KEY]
    settings.rate_limit_read = 100
    settings.rate_limit_write = 20
    settings.idempotency_ttl_seconds = 86400
    settings.idempotency_pending_ttl_seconds = 120
    settings.validation_dlq_max_body_bytes = 65536
    settings.rabbitmq_url = "amqp://test:test@localhost:5672/"

    for key, value in overrides.items():
        setattr(settings, key, value)

    return settings


@pytest.fixture
def gateway_app():
    fake_redis = FakeRedis()
    publisher = AsyncMock()
    publisher.publish = AsyncMock(return_value=datetime.now(tz=UTC))
    publisher.publish_validation_failure = AsyncMock(return_value=None)
    publisher.is_connected = True

    settings = _create_mock_settings()

    with patch("urgp.config.get_settings", return_value=settings):
        get_settings.cache_clear()
        app = create_app()
        app.state.redis = fake_redis
        app.state.publisher = publisher
        yield app, fake_redis, publisher, settings
        get_settings.cache_clear()


@pytest.fixture
def client(gateway_app):
    app, fake_redis, publisher, settings = gateway_app
    return TestClient(app), fake_redis, publisher, settings


class TestIngestValidPayload:
    """Valid payload → HTTP 202 + publish."""

    def test_valid_payload_returns_202(self, client) -> None:
        test_client, _, _, _ = client

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
        test_client, _, publisher, _ = client

        test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": _TEST_API_KEY},
        )

        publisher.publish.assert_awaited_once()

    def test_rate_limit_headers_present(self, client) -> None:
        test_client, _, _, _ = client

        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": _TEST_API_KEY},
        )

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_second_submission_returns_duplicate_200(self, client) -> None:
        test_client, _, publisher, _ = client

        first = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(build_id="dup-001"),
            headers={"X-API-Key": _TEST_API_KEY},
        )
        second = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(build_id="dup-001"),
            headers={"X-API-Key": _TEST_API_KEY},
        )

        assert first.status_code == 202
        assert second.status_code == 200
        assert second.json()["message"] == "Build event already processed (idempotent)"
        assert publisher.publish.await_count == 1


class TestIngestInvalidPayload:
    """Invalid payload → HTTP 422 + DLQ capture."""

    def test_missing_required_field_returns_structured_422(self, client) -> None:
        test_client, _, publisher, _ = client
        payload = _valid_payload()
        del payload["build_id"]

        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_failed"
        assert any(detail["field"] == "build_id" for detail in data["details"])
        publisher.publish_validation_failure.assert_awaited_once()

    def test_invalid_payload_still_contains_rate_limit_headers(self, client) -> None:
        test_client, _, _, _ = client
        payload = _valid_payload()
        payload["artifacts"] = []

        response = test_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-API-Key": _TEST_API_KEY},
        )

        assert response.status_code == 422
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


class TestIngestAuth:
    """Unauthenticated request → HTTP 401."""

    def test_missing_api_key_returns_401(self, client) -> None:
        test_client, _, _, _ = client

        response = test_client.post("/api/v1/ingest", json=_valid_payload())

        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_invalid_api_key_returns_401(self, client) -> None:
        test_client, _, _, _ = client

        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(),
            headers={"X-API-Key": "wrong-key"},
        )

        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]


class TestIngestRateLimiting:
    """Rate limiting semantics and headers."""

    def test_rate_limit_exceeded_returns_429_with_headers(self, gateway_app) -> None:
        app, fake_redis, publisher, _ = gateway_app

        with patch("urgp.config.get_settings", return_value=_create_mock_settings(rate_limit_write=1)):
            app.state.redis = fake_redis
            app.state.publisher = publisher
            test_client = TestClient(app)

            first = test_client.post(
                "/api/v1/ingest",
                json=_valid_payload(build_id="limit-1"),
                headers={"X-API-Key": _TEST_API_KEY},
            )
            second = test_client.post(
                "/api/v1/ingest",
                json=_valid_payload(build_id="limit-2"),
                headers={"X-API-Key": _TEST_API_KEY},
            )

        assert first.status_code == 202
        assert second.status_code == 429
        assert second.json()["detail"]["error"] == "rate_limit_exceeded"
        assert second.headers["Retry-After"]
        assert second.headers["X-RateLimit-Limit"] == "1"
        assert second.headers["X-RateLimit-Remaining"] == "0"


class TestIngestOperationalFailures:
    """Dependency failure semantics should be explicit and non-lossy."""

    def test_broker_failure_releases_reservation_and_returns_503(self, client) -> None:
        test_client, _, publisher, _ = client
        publisher.publish.side_effect = RuntimeError("rmq down")

        first = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(build_id="retry-001"),
            headers={"X-API-Key": _TEST_API_KEY},
        )
        publisher.publish.side_effect = None
        publisher.publish.return_value = datetime.now(tz=UTC)
        second = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(build_id="retry-001"),
            headers={"X-API-Key": _TEST_API_KEY},
        )

        assert first.status_code == 503
        assert first.json()["detail"]["error"] == "broker_unavailable"
        assert second.status_code == 202
        assert publisher.publish.await_count == 2

    def test_redis_unavailable_returns_503(self) -> None:
        settings = _create_mock_settings()
        publisher = AsyncMock()
        publisher.publish = AsyncMock(return_value=datetime.now(tz=UTC))
        publisher.publish_validation_failure = AsyncMock(return_value=None)
        publisher.is_connected = True

        with patch("urgp.config.get_settings", return_value=settings):
            get_settings.cache_clear()
            app = create_app()
            app.state.redis = None
            app.state.publisher = publisher
            test_client = TestClient(app, raise_server_exceptions=False)
            response = test_client.post(
                "/api/v1/ingest",
                json=_valid_payload(),
                headers={"X-API-Key": _TEST_API_KEY},
            )
            get_settings.cache_clear()

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "service_unavailable"

    def test_publisher_unavailable_returns_503(self) -> None:
        settings = _create_mock_settings()

        with patch("urgp.config.get_settings", return_value=settings):
            get_settings.cache_clear()
            app = create_app()
            app.state.redis = FakeRedis()
            app.state.publisher = None
            test_client = TestClient(app, raise_server_exceptions=False)
            response = test_client.post(
                "/api/v1/ingest",
                json=_valid_payload(),
                headers={"X-API-Key": _TEST_API_KEY},
            )
            get_settings.cache_clear()

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "broker_unavailable"

    @pytest.mark.asyncio
    async def test_existing_pending_reservation_returns_202_without_republish(self, gateway_app) -> None:
        app, fake_redis, publisher, settings = gateway_app
        service = IdempotencyService(
            fake_redis,
            completed_ttl_seconds=settings.idempotency_ttl_seconds,
            pending_ttl_seconds=settings.idempotency_pending_ttl_seconds,
        )
        await service.begin_processing("in-flight-001", "S32_IDE")

        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/ingest",
            json=_valid_payload(build_id="in-flight-001"),
            headers={"X-API-Key": _TEST_API_KEY},
        )

        assert response.status_code == 202
        assert response.json()["message"] == "Build event is already being processed"
        publisher.publish.assert_not_awaited()
