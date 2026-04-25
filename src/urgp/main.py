"""URGP FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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

    from urgp.api.activity import router as activity_router
    from urgp.api.admin import router as admin_router
    from urgp.api.builds import router as builds_router
    from urgp.api.error_handlers import request_validation_exception_handler
    from urgp.api.health import router as health_router
    from urgp.api.ingest import router as ingest_router
    from urgp.api.notifications import router as notifications_router
    from urgp.api.products import router as products_router

    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )

    portal_dir = Path(__file__).resolve().parents[2] / "frontend" / "portal"
    if portal_dir.exists():
        assets_dir = portal_dir / "assets"
        if assets_dir.exists():
            app.mount("/portal/assets", StaticFiles(directory=assets_dir), name="portal-assets")

        @app.get("/", include_in_schema=False)
        async def root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/portal")

        @app.get("/portal", include_in_schema=False)
        async def portal_index() -> FileResponse:
            return FileResponse(portal_dir / "index.html")

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(activity_router)
    app.include_router(builds_router)
    app.include_router(products_router)
    app.include_router(notifications_router)
    app.include_router(admin_router)

    return app


app = create_app()


def run() -> None:
    """Run the API server using validated application settings."""
    import uvicorn

    from urgp.config import get_settings

    settings = get_settings()
    reload_enabled = settings.debug and settings.environment == "development"

    uvicorn.run(
        "urgp.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
        workers=1 if reload_enabled else settings.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
