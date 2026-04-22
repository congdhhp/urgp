"""Unit tests for admin gateway endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from tests.unit.fakes import FakeRedis
from urgp.main import create_app

_TEST_API_KEY = "test-api-key-for-gateway-tests"


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.api_keys = [_TEST_API_KEY]
    settings.rate_limit_read = 100
    settings.rate_limit_write = 20
    settings.idempotency_ttl_seconds = 86400
    settings.idempotency_pending_ttl_seconds = 120
    settings.validation_dlq_max_body_bytes = 65536
    settings.rabbitmq_url = "amqp://test:test@localhost:5672/"
    return settings


class TestAdminDLQCount:
    """DLQ monitoring semantics should be operationally honest."""

    def test_returns_real_dlq_counts(self) -> None:
        queue = SimpleNamespace(
            declaration_result=SimpleNamespace(message_count=7, consumer_count=2),
        )
        channel = AsyncMock()
        channel.declare_queue = AsyncMock(return_value=queue)

        @asynccontextmanager
        async def _channel_ctx():
            yield channel

        connection = AsyncMock()
        connection.channel = _channel_ctx

        with patch("urgp.config.get_settings", return_value=_settings()):
            app = create_app()
            app.state.redis = FakeRedis()
            app.state.publisher = None
            client = TestClient(app, raise_server_exceptions=False)

            with patch("urgp.messaging.connection.create_rabbitmq_connection", return_value=connection):
                response = client.get(
                    "/api/v1/admin/dlq/count",
                    headers={"X-API-Key": _TEST_API_KEY},
                )

        assert response.status_code == 200
        assert response.json() == {
            "queue": "build.events.dlq",
            "message_count": 7,
            "consumer_count": 2,
        }

    def test_returns_503_when_rabbitmq_is_down(self) -> None:
        with patch("urgp.config.get_settings", return_value=_settings()):
            app = create_app()
            app.state.redis = FakeRedis()
            app.state.publisher = None
            client = TestClient(app, raise_server_exceptions=False)

            with patch("urgp.messaging.connection.create_rabbitmq_connection", side_effect=RuntimeError("rmq down")):
                response = client.get(
                    "/api/v1/admin/dlq/count",
                    headers={"X-API-Key": _TEST_API_KEY},
                )

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "broker_unavailable"
