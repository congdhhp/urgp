"""Platform worker for hydration and notification processing."""

from __future__ import annotations

import asyncio
import logging

from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from pydantic import ValidationError

from urgp.config import get_settings
from urgp.messaging.connection import create_rabbitmq_connection
from urgp.messaging.topology import (
    EXCHANGE_DLX,
    QUEUE_BUILD_NOTIFY,
    QUEUE_BUILD_PROCESS,
    setup_topology,
)
from urgp.runtime import AppResources
from urgp.schemas.ingest import IngestPayload
from urgp.services.build_processing import BuildEventProcessor
from urgp.services.cache import CacheService
from urgp.services.notification_processing import NotificationProcessingService
from urgp.services.signature import ManifestSignatureService

logger = logging.getLogger(__name__)


class HydrationWorker:
    """Consume build.process and persist manifests into PostgreSQL."""

    def __init__(self, resources: AppResources, processor: BuildEventProcessor) -> None:
        self._resources = resources
        self._processor = processor

    async def _handle_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                payload = IngestPayload.model_validate_json(message.body)
            except ValidationError:
                logger.exception("Worker received invalid build payload; rejecting to DLQ")
                raise

            result = await self._processor.process(payload)
            logger.info(
                "Persisted build manifest [build=%s, product=%s, manifest=%s, created=%s, traceability_incomplete=%s]",
                payload.build_id,
                payload.product_id,
                result.manifest_id,
                result.created,
                result.traceability_incomplete,
            )


class NotificationWorker:
    """Consume build.notify and deliver user notifications."""

    def __init__(self, notification_service: NotificationProcessingService) -> None:
        self._notification_service = notification_service

    async def _handle_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                payload = IngestPayload.model_validate_json(message.body)
            except ValidationError:
                logger.exception("Notification worker received invalid build payload; rejecting to DLQ")
                raise

            await self._notification_service.process_build_ready(payload.build_id, payload.product_id)
            logger.info(
                "Processed notifications for build [build=%s, product=%s]",
                payload.build_id,
                payload.product_id,
            )


class WorkerProcess:
    """Single process that consumes hydration and notification queues."""

    def __init__(
        self,
        resources: AppResources,
        hydration_worker: HydrationWorker,
        notification_worker: NotificationWorker,
    ) -> None:
        self._resources = resources
        self._hydration_worker = hydration_worker
        self._notification_worker = notification_worker
        self._connection: AbstractRobustConnection | None = None

    async def start(self) -> None:
        process_channel = None
        notify_channel = None
        try:
            await self._resources.open(
                with_database=True,
                with_redis=True,
                with_publisher=False,
                ensure_rabbitmq_topology=True,
            )

            self._connection = await create_rabbitmq_connection(self._resources.settings.rabbitmq_url)
            await setup_topology(self._connection)

            # Separate channels so prefetch limits are independent and
            # slow hydration processing cannot starve notification delivery.
            process_channel = await self._connection.channel()
            await process_channel.set_qos(prefetch_count=10)

            notify_channel = await self._connection.channel()
            await notify_channel.set_qos(prefetch_count=10)

            process_queue = await process_channel.declare_queue(
                QUEUE_BUILD_PROCESS,
                durable=True,
                arguments={"x-dead-letter-exchange": EXCHANGE_DLX},
            )
            notify_queue = await notify_channel.declare_queue(
                QUEUE_BUILD_NOTIFY,
                durable=True,
                arguments={"x-dead-letter-exchange": EXCHANGE_DLX},
            )

            await process_queue.consume(self._hydration_worker._handle_message)
            await notify_queue.consume(self._notification_worker._handle_message)

            logger.info(
                "Platform worker started [%s] and consuming queues [%s, %s]",
                self._resources.settings.environment,
                QUEUE_BUILD_PROCESS,
                QUEUE_BUILD_NOTIFY,
            )

            await asyncio.Event().wait()
        finally:
            for ch in (process_channel, notify_channel):
                if ch is not None and not ch.is_closed:
                    await ch.close()
            await self.close()

    async def close(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        await self._resources.close()


async def start_worker() -> None:
    """Create a worker instance and run it until interrupted."""
    settings = get_settings()
    resources = AppResources(settings)
    signer = ManifestSignatureService(settings.signing_key)

    cache = CacheService(
        redis_client_provider=lambda: resources.redis,
        default_ttl=settings.redis_cache_ttl,
    )

    processor = BuildEventProcessor(
        resources.require_session_factory,
        signer,
        settings,
        cache=cache,
    )
    notification_service = NotificationProcessingService(resources.require_session_factory, settings)
    hydration_worker = HydrationWorker(resources, processor)
    notification_worker = NotificationWorker(notification_service)
    worker = WorkerProcess(resources, hydration_worker, notification_worker)

    try:
        await worker.start()
    except asyncio.CancelledError:
        logger.info("Platform worker cancelled")
        raise


def run() -> None:
    """Entry point for the platform worker process."""
    try:
        asyncio.run(start_worker())
    except KeyboardInterrupt:
        logger.info("Platform worker stopped")


if __name__ == "__main__":
    run()
