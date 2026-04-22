"""Event publisher — RabbitMQ message publishing for build events.

Publishes validated ingestion payloads to both `build.process` and
`build.notify` queues via the `urgp.build.events` exchange.

Reference: docs/05-technical-design.md § Layer 2: Event Gateway
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractRobustConnection

from urgp.messaging.connection import create_rabbitmq_connection
from urgp.messaging.topology import (
    EXCHANGE_BUILD_EVENTS,
    ROUTING_KEY_NOTIFY,
    ROUTING_KEY_PROCESS,
)
from urgp.schemas.ingest import IngestPayload

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes build events to RabbitMQ processing and notification queues.

    The publisher enriches payloads with gateway metadata (ingestion timestamp
    and gateway instance ID) before publishing to both routing keys.
    """

    def __init__(self, rabbitmq_url: str) -> None:
        """Initialize the publisher.

        Args:
            rabbitmq_url: AMQP connection URL.
        """
        self._rabbitmq_url = rabbitmq_url
        self._connection: AbstractRobustConnection | None = None
        self._gateway_instance_id: str = str(uuid.uuid4())

    async def connect(self) -> None:
        """Establish RabbitMQ connection.

        Creates a robust, auto-reconnecting connection.
        """
        self._connection = await create_rabbitmq_connection(self._rabbitmq_url)
        logger.info("EventPublisher connected [instance=%s]", self._gateway_instance_id)

    async def publish(self, payload: IngestPayload, ingestion_timestamp: datetime | None = None) -> datetime:
        """Publish a validated payload to processing and notification queues.

        Args:
            payload: Validated ingestion payload.
            ingestion_timestamp: Server-side ingestion timestamp (auto-generated if None).

        Returns:
            The ingestion timestamp used.

        Raises:
            RuntimeError: If publisher is not connected.
            aio_pika.exceptions.AMQPError: On RabbitMQ publish failure.
        """
        if not self._connection or self._connection.is_closed:
            msg = "EventPublisher is not connected. Call connect() first."
            raise RuntimeError(msg)

        if ingestion_timestamp is None:
            ingestion_timestamp = datetime.now(tz=UTC)

        # Enrich payload with gateway metadata
        enriched = self._enrich_payload(payload, ingestion_timestamp)

        # Serialize to JSON bytes
        message_body = json.dumps(enriched, default=str).encode("utf-8")

        async with self._connection.channel() as channel:
            exchange = await channel.get_exchange(EXCHANGE_BUILD_EVENTS)

            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=str(uuid.uuid4()),
                timestamp=ingestion_timestamp,
                headers={
                    "build_id": payload.build_id,
                    "product_id": payload.product_id,
                    "gateway_instance_id": self._gateway_instance_id,
                },
            )

            # Publish to processing queue
            await exchange.publish(message, routing_key=ROUTING_KEY_PROCESS)

            # Publish to notification queue
            await exchange.publish(message, routing_key=ROUTING_KEY_NOTIFY)

            logger.info(
                "Published build event [build=%s, product=%s] → [%s, %s]",
                payload.build_id,
                payload.product_id,
                ROUTING_KEY_PROCESS,
                ROUTING_KEY_NOTIFY,
            )

        return ingestion_timestamp

    async def close(self) -> None:
        """Gracefully close the RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("EventPublisher disconnected")
        self._connection = None

    def _enrich_payload(self, payload: IngestPayload, ingestion_timestamp: datetime) -> dict[str, Any]:
        """Enrich the payload with gateway metadata.

        Args:
            payload: Original ingestion payload.
            ingestion_timestamp: Server-side timestamp.

        Returns:
            Enriched payload dictionary.
        """
        data = payload.model_dump(mode="json")
        data["ingestion_timestamp"] = ingestion_timestamp.isoformat()
        data["gateway_instance_id"] = self._gateway_instance_id
        return data

    @property
    def is_connected(self) -> bool:
        """Check if the publisher has an active connection."""
        return self._connection is not None and not self._connection.is_closed

    @property
    def gateway_instance_id(self) -> str:
        """Return the unique gateway instance identifier."""
        return self._gateway_instance_id
