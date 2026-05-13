"""Admin monitoring endpoints — DLQ and system status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from urgp.dependencies import ReadAccessDep, _service_unavailable
from urgp.messaging.topology import QUEUE_DLQ
from urgp.schemas.responses import DLQCountResponse, ServiceUnavailableResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get(
    "/dlq/count",
    response_model=DLQCountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Missing or invalid API key"},
        429: {"description": "Rate limit exceeded"},
        503: {
            "model": ServiceUnavailableResponse,
            "description": "RabbitMQ is unavailable",
        },
    },
    summary="Get DLQ message count",
    description="Returns the number of messages in the Dead Letter Queue for monitoring purposes.",
)
async def get_dlq_count(_api_key: ReadAccessDep) -> DLQCountResponse:
    """Get the Dead Letter Queue message count."""
    try:
        from urgp.config import get_settings
        from urgp.messaging.connection import create_rabbitmq_connection

        settings = get_settings()
        connection = await create_rabbitmq_connection(settings.rabbitmq_url)
        try:
            async with connection.channel() as channel:
                queue = await channel.declare_queue(QUEUE_DLQ, passive=True)
                message_count = queue.declaration_result.message_count
                consumer_count = queue.declaration_result.consumer_count
        finally:
            await connection.close()

        return DLQCountResponse(
            queue=QUEUE_DLQ,
            message_count=message_count,
            consumer_count=consumer_count,
        )
    except Exception as exc:
        logger.error("Failed to get DLQ count: %s", exc)
        raise _service_unavailable(
            "RabbitMQ is unavailable. DLQ metrics cannot be retrieved right now.",
            error="broker_unavailable",
        ) from exc
