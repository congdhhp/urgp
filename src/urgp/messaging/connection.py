"""RabbitMQ connection factory.

Provides async connection management for RabbitMQ using aio-pika.
"""

from __future__ import annotations

import logging

import aio_pika
from aio_pika.abc import AbstractRobustConnection

logger = logging.getLogger(__name__)


async def create_rabbitmq_connection(url: str) -> AbstractRobustConnection:
    """Create a robust RabbitMQ connection.

    Args:
        url: AMQP connection URL (e.g., amqp://user:pass@host:5672/)

    Returns:
        AbstractRobustConnection: A robust, auto-reconnecting connection.
    """
    connection = await aio_pika.connect_robust(url)
    logger.info("Connected to RabbitMQ at %s", url.split("@")[-1] if "@" in url else url)
    return connection


async def check_rabbitmq_health(url: str) -> bool:
    """Check if RabbitMQ is reachable.

    Args:
        url: AMQP connection URL.

    Returns:
        bool: True if connection succeeds, False otherwise.
    """
    try:
        connection = await aio_pika.connect_robust(url, timeout=5)
        await connection.close()
        return True
    except Exception:
        logger.warning("RabbitMQ health check failed")
        return False
