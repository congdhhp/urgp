"""Unit tests for the EventPublisher (P1-3.T5).

Tests cover:
- P1-3.T5: Message published to both build.process and build.notify routing keys
- Payload enrichment with gateway metadata
- Connection state management
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from urgp.messaging.topology import ROUTING_KEY_NOTIFY, ROUTING_KEY_PROCESS
from urgp.models.enums import ArtifactType, BuildType
from urgp.schemas.ingest import IngestPayload
from urgp.services.publisher import EventPublisher

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _valid_payload() -> IngestPayload:
    """Create a valid IngestPayload for testing."""
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


# ─────────────────────────────────────────────
# P1-3.T5: Publisher Tests
# ─────────────────────────────────────────────


class TestEventPublisher:
    """P1-3.T5: RabbitMQ message publishing tests."""

    async def test_publish_sends_to_both_queues(self) -> None:
        """Published message is sent to both process and notify routing keys."""
        from contextlib import asynccontextmanager

        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange = AsyncMock(return_value=mock_exchange)

        @asynccontextmanager
        async def _mock_channel_ctx():
            yield mock_channel

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = _mock_channel_ctx

        publisher._connection = mock_connection

        await publisher.publish(_valid_payload())

        # Verify get_exchange was called once
        mock_channel.get_exchange.assert_awaited_once()

        # Verify publish was called twice on the exchange (process + notify)
        assert mock_exchange.publish.await_count == 2
        calls = mock_exchange.publish.await_args_list
        routing_keys = [c.kwargs.get("routing_key") for c in calls]
        assert ROUTING_KEY_PROCESS in routing_keys
        assert ROUTING_KEY_NOTIFY in routing_keys

    async def test_publish_returns_timestamp(self) -> None:
        """Publish returns the ingestion timestamp."""
        from contextlib import asynccontextmanager

        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange = AsyncMock(return_value=mock_exchange)

        @asynccontextmanager
        async def _mock_channel_ctx():
            yield mock_channel

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = _mock_channel_ctx

        publisher._connection = mock_connection

        result = await publisher.publish(_valid_payload())

        assert isinstance(result, datetime)

    async def test_publish_fails_when_not_connected(self) -> None:
        """Publish raises RuntimeError when not connected."""
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        with pytest.raises(RuntimeError, match="not connected"):
            await publisher.publish(_valid_payload())

    def test_gateway_instance_id_is_unique(self) -> None:
        """Each publisher instance gets a unique gateway ID."""
        p1 = EventPublisher("amqp://test@localhost/")
        p2 = EventPublisher("amqp://test@localhost/")
        assert p1.gateway_instance_id != p2.gateway_instance_id

    def test_is_connected_false_initially(self) -> None:
        """Publisher starts disconnected."""
        publisher = EventPublisher("amqp://test@localhost/")
        assert publisher.is_connected is False

    async def test_payload_enrichment(self) -> None:
        """Published payload includes gateway metadata."""
        publisher = EventPublisher("amqp://test:test@localhost:5672/")

        payload = _valid_payload()
        enriched = publisher._enrich_payload(payload, datetime.now(tz=UTC))

        assert "ingestion_timestamp" in enriched
        assert "gateway_instance_id" in enriched
        assert enriched["product_id"] == "S32_IDE"
        assert enriched["build_id"] == "260330"

    async def test_close_when_connected(self) -> None:
        """Close gracefully closes the connection."""
        publisher = EventPublisher("amqp://test:test@localhost:5672/")
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        publisher._connection = mock_connection

        await publisher.close()

        mock_connection.close.assert_called_once()
        assert publisher._connection is None

    async def test_close_when_not_connected(self) -> None:
        """Close is safe to call when not connected."""
        publisher = EventPublisher("amqp://test@localhost/")
        await publisher.close()  # Should not raise
