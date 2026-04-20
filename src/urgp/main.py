"""URGP FastAPI application entry point.

Initializes the FastAPI app with middleware, routers, and lifecycle events.

Reference:
    - docs/05-technical-design.md § Project Structure
    - docs/07-implementation-plan.md § P1-1.6
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

    logger.info("URGP API startup complete")

    yield

    # ── Shutdown ───────────────────────────────────────────
    logger.info("URGP API shutting down")


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
    from urgp.api.health import router as health_router

    app.include_router(health_router)

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
