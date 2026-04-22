"""Admin monitoring endpoints — DLQ and system status.

Provides operational visibility into the Event Gateway's health,
including Dead Letter Queue monitoring.

Reference: docs/07-implementation-plan.md § P1-3.5
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from urgp.dependencies import RedisDep
from urgp.messaging.topology import QUEUE_DLQ
from urgp.middleware.api_key_auth import APIKeyDep
from urgp.schemas.responses import DLQCountResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get(
    "/dlq/count",
    response_model=DLQCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get DLQ message count",
    description="Returns the number of messages in the Dead Letter Queue for monitoring purposes.",
)
async def get_dlq_count(
    api_key: APIKeyDep,
    redis_client: RedisDep,
) -> DLQCountResponse:
    """Get the Dead Letter Queue message count.

    Connects to RabbitMQ via aio_pika to inspect the DLQ.
    This is an administrative endpoint — protected by API key.

    Args:
        api_key: Validated API key (from dependency).
        redis_client: Redis client (used indirectly through deps).

    Returns:
        DLQCountResponse with message and consumer counts.
    """
    try:
        from urgp.config import get_settings
        from urgp.messaging.connection import create_rabbitmq_connection

        settings = get_settings()
        connection = await create_rabbitmq_connection(settings.rabbitmq_url)

        async with connection.channel() as channel:
            # Passive declare to get queue info without modifying it
            queue = await channel.declare_queue(QUEUE_DLQ, passive=True)
            message_count = queue.declaration_result.message_count
            consumer_count = queue.declaration_result.consumer_count

        await connection.close()

        return DLQCountResponse(
            queue=QUEUE_DLQ,
            message_count=message_count,
            consumer_count=consumer_count,
        )

    except Exception as e:
        logger.error("Failed to get DLQ count: %s", str(e))
        # Return zero counts if RabbitMQ is unreachable
        return DLQCountResponse(
            queue=QUEUE_DLQ,
            message_count=0,
            consumer_count=0,
        )
