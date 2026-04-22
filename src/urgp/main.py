"""URGP FastAPI application entry point.

Initializes the FastAPI app with middleware, routers, and lifecycle events.
Manages shared dependencies (Redis, RabbitMQ publisher) via app.state.

Reference:
    - docs/05-technical-design.md § Project Structure
    - docs/07-implementation-plan.md § P1-1.6, P1-3
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from urgp import __version__

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown events."""
    # ── Startup ────────────────────────────────────────────
    from urgp.config import get_settings
    from urgp.logging import setup_logging

    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)

    logger.info(
        "Starting URGP API v%s [%s]",
        settings.app_version,
        settings.environment,
    )

    # Set up RabbitMQ topology (idempotent)
    try:
        from urgp.messaging.connection import create_rabbitmq_connection
        from urgp.messaging.topology import setup_topology

        rmq_connection = await create_rabbitmq_connection(settings.rabbitmq_url)
        await setup_topology(rmq_connection)
        await rmq_connection.close()
        logger.info("RabbitMQ topology initialized")
    except Exception:
        logger.warning("Could not initialize RabbitMQ topology — will retry on first use")

    # Initialize shared Redis client
    try:
        import redis.asyncio as aioredis

        app.state.redis = aioredis.from_url(
            str(settings.redis_url),
            decode_responses=False,
            socket_timeout=5,
        )
        await app.state.redis.ping()
        logger.info("Redis client initialized")
    except Exception:
        logger.warning("Could not connect to Redis — idempotency and rate limiting may fail")
        app.state.redis = None

    # Initialize EventPublisher (RabbitMQ)
    try:
        from urgp.services.publisher import EventPublisher

        app.state.publisher = EventPublisher(settings.rabbitmq_url)
        await app.state.publisher.connect()
        logger.info("EventPublisher initialized")
    except Exception:
        logger.warning("Could not initialize EventPublisher — ingestion will fail")
        app.state.publisher = None

    logger.info("URGP API startup complete")

    yield

    # ── Shutdown ───────────────────────────────────────────
    logger.info("URGP API shutting down")

    # Close EventPublisher
    if hasattr(app.state, "publisher") and app.state.publisher:
        try:
            await app.state.publisher.close()
            logger.info("EventPublisher closed")
        except Exception:
            logger.warning("Error closing EventPublisher")

    # Close Redis
    if hasattr(app.state, "redis") and app.state.redis:
        try:
            await app.state.redis.close()
            logger.info("Redis client closed")
        except Exception:
            logger.warning("Error closing Redis client")

    logger.info("URGP API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance.
    """
    app = FastAPI(
        title="URGP — Universal Release Governance Platform",
        description="Centralized release governance, traceability, and immutability for software delivery.",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────
    # Request ID middleware (must be added before CORS)
    from urgp.middleware.request_id import RequestIDMiddleware

    app.add_middleware(RequestIDMiddleware)

    # CORS middleware
    try:
        from urgp.config import get_settings

        settings = get_settings()
        cors_origins = settings.cors_origins
    except Exception:
        cors_origins = ["http://localhost:3000", "http://localhost:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────
    from urgp.api.admin import router as admin_router
    from urgp.api.health import router as health_router
    from urgp.api.ingest import router as ingest_router

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(admin_router)

    return app


# Application instance
app = create_app()


def run() -> None:
    """Run the development server."""
    import uvicorn

    uvicorn.run(
        "urgp.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run()
