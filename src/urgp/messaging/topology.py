"""RabbitMQ topology setup — exchanges, queues, and bindings.

Reference: docs/05-technical-design.md § Layer 2: Event Gateway

Topology:
    Exchange: urgp.build.events (direct)
        → Queue: build.process (routing_key: build.process)
        → Queue: build.notify  (routing_key: build.notify)

    Exchange: urgp.build.events.dlx (fanout) — Dead Letter Exchange
        → Queue: build.events.dlq

    Queues have x-dead-letter-exchange pointing to the DLX.
"""

from __future__ import annotations

import logging

import aio_pika
from aio_pika.abc import AbstractRobustConnection

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Topology Constants
# ─────────────────────────────────────────────

EXCHANGE_BUILD_EVENTS = "urgp.build.events"
EXCHANGE_DLX = "urgp.build.events.dlx"

QUEUE_BUILD_PROCESS = "build.process"
QUEUE_BUILD_NOTIFY = "build.notify"
QUEUE_DLQ = "build.events.dlq"

ROUTING_KEY_PROCESS = "build.process"
ROUTING_KEY_NOTIFY = "build.notify"


async def setup_topology(connection: AbstractRobustConnection) -> None:
    """Declare RabbitMQ exchanges, queues, and bindings.

    This function is idempotent — safe to call multiple times.

    Args:
        connection: Active RabbitMQ connection.
    """
    async with connection.channel() as channel:
        # ── Dead Letter Exchange (DLX) ─────────────────────
        dlx_exchange = await channel.declare_exchange(
            EXCHANGE_DLX,
            aio_pika.ExchangeType.FANOUT,
            durable=True,
        )

        # ── DLQ (Dead Letter Queue) ───────────────────────
        dlq_queue = await channel.declare_queue(
            QUEUE_DLQ,
            durable=True,
        )
        await dlq_queue.bind(dlx_exchange)

        # ── Main Exchange ─────────────────────────────────
        main_exchange = await channel.declare_exchange(
            EXCHANGE_BUILD_EVENTS,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # ── Processing Queue ──────────────────────────────
        process_queue = await channel.declare_queue(
            QUEUE_BUILD_PROCESS,
            durable=True,
            arguments={
                "x-dead-letter-exchange": EXCHANGE_DLX,
            },
        )
        await process_queue.bind(main_exchange, routing_key=ROUTING_KEY_PROCESS)

        # ── Notification Queue ────────────────────────────
        notify_queue = await channel.declare_queue(
            QUEUE_BUILD_NOTIFY,
            durable=True,
            arguments={
                "x-dead-letter-exchange": EXCHANGE_DLX,
            },
        )
        await notify_queue.bind(main_exchange, routing_key=ROUTING_KEY_NOTIFY)

        logger.info(
            "RabbitMQ topology declared: exchanges=[%s, %s], queues=[%s, %s, %s]",
            EXCHANGE_BUILD_EVENTS, EXCHANGE_DLX,
            QUEUE_BUILD_PROCESS, QUEUE_BUILD_NOTIFY, QUEUE_DLQ,
        )
