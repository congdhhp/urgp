"""Hydration worker for consuming and persisting build events."""

from __future__ import annotations

import asyncio
import logging

from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from pydantic import ValidationError

from urgp.config import get_settings
from urgp.messaging.connection import create_rabbitmq_connection
from urgp.messaging.topology import EXCHANGE_DLX, QUEUE_BUILD_PROCESS, setup_topology
from urgp.runtime import AppResources
from urgp.schemas.ingest import IngestPayload
from urgp.services.build_processing import BuildEventProcessor
from urgp.services.signature import ManifestSignatureService

logger = logging.getLogger(__name__)


class HydrationWorker:
    """RabbitMQ consumer that persists build manifests into PostgreSQL."""

    def __init__(self, resources: AppResources, processor: BuildEventProcessor) -> None:
        self._resources = resources
        self._processor = processor
        self._connection: AbstractRobustConnection | None = None

    async def start(self) -> None:
        """Open dependencies and consume build events until cancelled."""
        settings = self._resources.settings
        channel = None
        try:
            await self._resources.open(
                with_database=True,
                with_redis=False,
                with_publisher=False,
                ensure_rabbitmq_topology=True,
            )

            self._connection = await create_rabbitmq_connection(settings.rabbitmq_url)
            await setup_topology(self._connection)

            channel = await self._connection.channel()
            await channel.set_qos(prefetch_count=10)
            queue = await channel.declare_queue(
                QUEUE_BUILD_PROCESS,
                durable=True,
                arguments={"x-dead-letter-exchange": EXCHANGE_DLX},
            )
            await queue.consume(self._handle_message)

            logger.info(
                "Hydration worker started [%s] and consuming queue '%s'",
                settings.environment,
                QUEUE_BUILD_PROCESS,
            )

            await asyncio.Event().wait()
        finally:
            if channel is not None and not channel.is_closed:
                await channel.close()
            await self.close()

    async def close(self) -> None:
        """Close worker-owned resources."""
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        await self._resources.close()

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


async def start_worker() -> None:
    """Create a worker instance and run it until interrupted."""
    settings = get_settings()
    resources = AppResources(settings)
    signer = ManifestSignatureService(settings.signing_key)
    processor = BuildEventProcessor(resources.require_session_factory, signer)
    worker = HydrationWorker(resources, processor)

    try:
        await worker.start()
    except asyncio.CancelledError:
        logger.info("Hydration worker cancelled")
        raise


def run() -> None:
    """Entry point for the hydration worker process."""
    try:
        asyncio.run(start_worker())
    except KeyboardInterrupt:
        logger.info("Hydration worker stopped")


if __name__ == "__main__":
    run()
