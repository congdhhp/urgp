"""Hydration worker — RabbitMQ consumer for build processing.

This is the async worker process that:
1. Consumes messages from build.process queue
2. Creates build manifests in the database
3. Triggers traceability hydration (Git + Jira resolution)

This is a STUB for Phase P1-1 (infrastructure).
Full implementation happens in P1-4 (Control Plane).
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def start_worker() -> None:
    """Start the hydration worker (stub).

    This will be implemented in the P1-4 Control Plane worktree.
    For now, it just logs a startup message and waits.
    """
    from urgp.config import get_settings
    from urgp.logging import setup_logging

    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)

    logger.info(
        "URGP Worker starting [%s] — waiting for messages on build.process queue...",
        settings.environment,
    )

    # Keep the worker alive (placeholder — will be replaced with RabbitMQ consumer)
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        logger.info("URGP Worker shutting down")


def run() -> None:
    """Entry point for the hydration worker."""
    asyncio.run(start_worker())


if __name__ == "__main__":
    run()
