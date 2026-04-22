"""Unit tests for the EventPublisher (P1-3.T5)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from urgp.messaging.topology import EXCHANGE_DLX, ROUTING_KEY_NOTIFY, ROUTING_KEY_PROCESS
from urgp.models.enums import ArtifactType, BuildType
from urgp.schemas.ingest import IngestPayload
from urgp.services.publisher import EventPublisher


def _valid_payload() -> IngestPayload:
    return IngestPayload(
        product_id="S32_IDE",
        release="3.6.8-RFP",
        build_type=BuildType.NIGHTLY,
        build_id="260330",
        cli_version="1.0.0",
        commit_hashes=[
            {
                "repository": "bitbucket.org/nxp/s32k3_dev",
                "hash": "a" * 40,
            }
        ],
        artifacts=[
            {
                "name": "s32-ide.zip",
                "type": ArtifactType.ECLIPSE_P2,
                "storage_uri": "https://artifacts.internal/builds/260330/s32-ide.zip",
                "sha256": "a" * 64,
            }
        ],
        timestamp=datetime.now(tz=UTC),
    )


def _build_mock_connection(mock_channel: AsyncMock) -> AsyncMock:
    @asynccontextmanager
    async def _mock_channel_ctx(*_args, **_kwargs):
        yield mock_channel

    connection = AsyncMock()
    connection.is_closed = False
    connection.channel = _mock_channel_ctx
    return connection


def _attach_transaction(mock_channel: AsyncMock) -> MagicMock:
    transaction = MagicMock()

    @asynccontextmanager
    async def _transaction_ctx():
        yield transaction

    mock_channel.transaction = _transaction_ctx
    return transaction


class TestEventPublisher:
    """P1-3.T5: RabbitMQ message publishing tests."""

    async def test_publish_sends_to_both_queues(self) -> None:
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange = AsyncMock(return_value=mock_exchange)
        _attach_transaction(mock_channel)
        publisher._connection = _build_mock_connection(mock_channel)

        await publisher.publish(_valid_payload())

        mock_channel.get_exchange.assert_awaited_once()
        assert mock_exchange.publish.await_count == 2
        routing_keys = [call.kwargs["routing_key"] for call in mock_exchange.publish.await_args_list]
        assert routing_keys == [ROUTING_KEY_PROCESS, ROUTING_KEY_NOTIFY]

    async def test_publish_returns_timestamp(self) -> None:
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange = AsyncMock(return_value=mock_exchange)
        _attach_transaction(mock_channel)
        publisher._connection = _build_mock_connection(mock_channel)

        result = await publisher.publish(_valid_payload())

        assert isinstance(result, datetime)

    async def test_publish_fails_when_not_connected(self) -> None:
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        with pytest.raises(RuntimeError, match="not connected"):
            await publisher.publish(_valid_payload())

    async def test_publish_validation_failure_uses_dlx_exchange(self) -> None:
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange = AsyncMock(return_value=mock_exchange)
        publisher._connection = _build_mock_connection(mock_channel)

        await publisher.publish_validation_failure(
            raw_body='{"build_id":"broken"}',
            validation_errors=[{"field": "build_id", "message": "Field required"}],
            request_context={"path": "/api/v1/ingest", "request_id": "req-123"},
        )

        mock_channel.get_exchange.assert_awaited_once_with(EXCHANGE_DLX)
        mock_exchange.publish.assert_awaited_once()
        assert mock_exchange.publish.await_args.kwargs["routing_key"] == ""

    def test_gateway_instance_id_is_unique(self) -> None:
        p1 = EventPublisher("amqp://test@localhost/")
        p2 = EventPublisher("amqp://test@localhost/")
        assert p1.gateway_instance_id != p2.gateway_instance_id

    def test_is_connected_false_initially(self) -> None:
        publisher = EventPublisher("amqp://test@localhost/")
        assert publisher.is_connected is False

    async def test_payload_enrichment(self) -> None:
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        payload = _valid_payload()
        enriched = publisher._enrich_payload(payload, datetime.now(tz=UTC))

        assert "ingestion_timestamp" in enriched
        assert "gateway_instance_id" in enriched
        assert enriched["product_id"] == "S32_IDE"
        assert enriched["build_id"] == "260330"

    async def test_close_when_connected(self) -> None:
        publisher = EventPublisher("amqp://test:test@localhost:5672/")
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        publisher._connection = mock_connection

        await publisher.close()

        mock_connection.close.assert_awaited_once()
        assert publisher._connection is None

    async def test_close_when_not_connected(self) -> None:
        publisher = EventPublisher("amqp://test@localhost/")
        await publisher.close()
