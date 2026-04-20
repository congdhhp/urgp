"""Unit tests for RabbitMQ topology constants and structure."""

from __future__ import annotations

from urgp.messaging.topology import (
    EXCHANGE_BUILD_EVENTS,
    EXCHANGE_DLX,
    QUEUE_BUILD_NOTIFY,
    QUEUE_BUILD_PROCESS,
    QUEUE_DLQ,
    ROUTING_KEY_NOTIFY,
    ROUTING_KEY_PROCESS,
)


class TestTopologyConstants:
    """Tests for RabbitMQ topology naming conventions."""

    def test_exchange_names(self) -> None:
        """Exchange names follow urgp.* convention."""
        assert EXCHANGE_BUILD_EVENTS == "urgp.build.events"
        assert EXCHANGE_DLX == "urgp.build.events.dlx"

    def test_queue_names(self) -> None:
        """Queue names follow build.* convention."""
        assert QUEUE_BUILD_PROCESS == "build.process"
        assert QUEUE_BUILD_NOTIFY == "build.notify"
        assert QUEUE_DLQ == "build.events.dlq"

    def test_routing_keys(self) -> None:
        """Routing keys match queue names."""
        assert ROUTING_KEY_PROCESS == "build.process"
        assert ROUTING_KEY_NOTIFY == "build.notify"
