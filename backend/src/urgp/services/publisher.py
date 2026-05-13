"""Event publisher — RabbitMQ message publishing for build events."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

import aio_pika
from aio_pika.abc import AbstractRobustConnection

from urgp.messaging.connection import create_rabbitmq_connection
from urgp.messaging.topology import (
    EXCHANGE_BUILD_EVENTS,
    EXCHANGE_DLX,
    ROUTING_KEY_NOTIFY,
    ROUTING_KEY_PROCESS,
)
from urgp.schemas.ingest import IngestPayload
from urgp.schemas.notifications import NotificationRequest

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publish build events and operational DLQ messages to RabbitMQ."""

    def __init__(self, rabbitmq_url: str) -> None:
        self._rabbitmq_url = rabbitmq_url
        self._connection: AbstractRobustConnection | None = None
        self._gateway_instance_id = str(uuid.uuid4())

    async def connect(self) -> None:
        self._connection = await create_rabbitmq_connection(self._rabbitmq_url)
        logger.info("EventPublisher connected [instance=%s]", self._gateway_instance_id)

    async def publish(self, payload: IngestPayload, ingestion_timestamp: datetime | None = None) -> datetime:
        """Publish a validated build payload to the processing queue."""
        self._ensure_connected()
        connection = self._connection
        assert connection is not None

        if ingestion_timestamp is None:
            ingestion_timestamp = datetime.now(tz=UTC)

        enriched_payload = self._enrich_payload(payload, ingestion_timestamp)

        async with connection.channel(publisher_confirms=False) as channel:
            exchange = await channel.get_exchange(EXCHANGE_BUILD_EVENTS)
            await exchange.publish(
                self._build_message(
                    enriched_payload,
                    message_type="build_event",
                    timestamp=ingestion_timestamp,
                    headers={
                        "build_id": payload.build_id,
                        "product_id": payload.product_id,
                        "gateway_instance_id": self._gateway_instance_id,
                    },
                ),
                routing_key=ROUTING_KEY_PROCESS,
            )

        logger.info(
            "Published build event [build=%s, product=%s] -> [%s]",
            payload.build_id,
            payload.product_id,
            ROUTING_KEY_PROCESS,
        )
        return ingestion_timestamp

    async def publish_notification_request(self, request: NotificationRequest) -> datetime:
        """Publish an internal notification request to the notification queue."""
        self._ensure_connected()
        connection = self._connection
        assert connection is not None

        published_at = datetime.now(tz=UTC)
        async with connection.channel(publisher_confirms=False) as channel:
            exchange = await channel.get_exchange(EXCHANGE_BUILD_EVENTS)
            await exchange.publish(
                self._build_message(
                    request.model_dump(mode="json"),
                    message_type="notification_request",
                    timestamp=published_at,
                    headers={
                        "manifest_id": str(request.manifest_id),
                        "build_id": request.build_id,
                        "product_id": request.product_id,
                        "event_type": request.event_type.value,
                        "gateway_instance_id": self._gateway_instance_id,
                    },
                ),
                routing_key=ROUTING_KEY_NOTIFY,
            )

        logger.info(
            "Published notification request [manifest=%s, build=%s, product=%s, event=%s] -> [%s]",
            request.manifest_id,
            request.build_id,
            request.product_id,
            request.event_type.value,
            ROUTING_KEY_NOTIFY,
        )
        return published_at

    async def publish_validation_failure(
        self,
        *,
        raw_body: str,
        validation_errors: Sequence[dict[str, object]],
        request_context: dict[str, object],
    ) -> None:
        """Publish validation failures to the DLQ exchange for investigation."""
        self._ensure_connected()
        connection = self._connection
        assert connection is not None

        payload = {
            "error": "validation_failed",
            "message": "Rejected invalid ingestion payload.",
            "raw_body": raw_body,
            "validation_errors": list(validation_errors),
            "request_context": request_context,
            "gateway_instance_id": self._gateway_instance_id,
            "captured_at": datetime.now(tz=UTC).isoformat(),
        }

        async with connection.channel() as channel:
            exchange = await channel.get_exchange(EXCHANGE_DLX)
            await exchange.publish(
                self._build_message(
                    payload,
                    message_type="validation_failure",
                    timestamp=datetime.now(tz=UTC),
                    headers={
                        "gateway_instance_id": self._gateway_instance_id,
                        "error": "validation_failed",
                    },
                ),
                routing_key="",
            )

        logger.warning(
            "Published validation failure to DLQ [path=%s, request_id=%s]",
            request_context.get("path"),
            request_context.get("request_id"),
        )

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("EventPublisher disconnected")
        self._connection = None

    def _ensure_connected(self) -> None:
        if not self._connection or self._connection.is_closed:
            msg = "EventPublisher is not connected. Call connect() first."
            raise RuntimeError(msg)

    def _enrich_payload(self, payload: IngestPayload, ingestion_timestamp: datetime) -> dict[str, Any]:
        data = payload.model_dump(mode="json")
        data["ingestion_timestamp"] = ingestion_timestamp.isoformat()
        data["gateway_instance_id"] = self._gateway_instance_id
        return data

    @staticmethod
    def _build_message(
        payload: dict[str, Any],
        *,
        message_type: str,
        timestamp: datetime,
        headers: dict[str, object],
    ) -> aio_pika.Message:
        return aio_pika.Message(
            body=json.dumps(payload, default=str).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            type=message_type,
            message_id=str(uuid.uuid4()),
            timestamp=timestamp,
            headers=cast("dict[str, Any]", headers),
        )

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    @property
    def gateway_instance_id(self) -> str:
        return self._gateway_instance_id
