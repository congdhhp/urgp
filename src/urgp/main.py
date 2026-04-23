"""URGP FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from urgp import __version__

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan for startup and shutdown resource handling."""
    from urgp.config import get_settings
    from urgp.runtime import AppResources

    settings = get_settings()
    resources = AppResources(settings)
    app.state.resources = resources

    await resources.open(
        with_database=True,
        with_redis=True,
        with_publisher=True,
        ensure_rabbitmq_topology=True,
    )
    app.state.redis = resources.redis
    app.state.publisher = resources.publisher
    app.state.session_factory = resources.session_factory

    logger.info(
        "Starting URGP API v%s [%s]",
        settings.app_version,
        settings.environment,
    )

    logger.info("URGP API startup complete")
    yield

    logger.info("URGP API shutting down")
    await resources.close()
    logger.info("URGP API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="URGP - Universal Release Governance Platform",
        description="Centralized release governance, traceability, and immutability for software delivery.",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    from urgp.middleware.request_id import RequestIDMiddleware
    from urgp.middleware.response_headers import ResponseHeadersMiddleware

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(ResponseHeadersMiddleware)

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

    from urgp.api.admin import router as admin_router
    from urgp.api.error_handlers import request_validation_exception_handler
    from urgp.api.health import router as health_router
    from urgp.api.ingest import router as ingest_router

    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(admin_router)

    return app


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
