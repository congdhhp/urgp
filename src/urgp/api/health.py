"""Health check endpoints.

GET /health       — Basic liveness check (< 100ms)
GET /health/ready — Readiness check (DB + RabbitMQ + Redis)

Reference: docs/07-implementation-plan.md § P1-1.6
"""

from __future__ import annotations

import time
from typing import Any, cast

from fastapi import APIRouter, Request, Response
from sqlalchemy import text as sa_text

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """Basic health/liveness check.

    Returns 200 OK to indicate the API process is running.
    Should respond in < 100ms — no dependency checks.
    """
    return {
        "status": "healthy",
        "service": "urgp-api",
    }


@router.get("/health/ready", response_model=dict[str, Any])
async def readiness_check(request: Request, response: Response) -> dict[str, Any]:
    """Readiness check — verifies critical dependencies.

    Checks connectivity to:
    - PostgreSQL database
    - RabbitMQ message broker
    - Redis cache

    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    start = time.monotonic()
    checks: dict[str, dict[str, Any]] = {}
    all_healthy = True

    # Check PostgreSQL
    try:
        from urgp.config import get_settings
        from urgp.db.session import create_engine

        settings = get_settings()
        shared_engine = getattr(getattr(request.app.state, "resources", None), "engine", None)
        engine = shared_engine or create_engine(settings.database_url_str, pool_size=1, pool_overflow=0)
        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        if shared_engine is None:
            await engine.dispose()
        checks["database"] = {"status": "healthy", "type": "postgresql"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Check RabbitMQ
    try:
        from urgp.config import get_settings
        from urgp.messaging.connection import check_rabbitmq_health

        settings = get_settings()
        rmq_healthy = await check_rabbitmq_health(settings.rabbitmq_url)
        if rmq_healthy:
            checks["rabbitmq"] = {"status": "healthy"}
        else:
            checks["rabbitmq"] = {"status": "unhealthy", "error": "Connection failed"}
            all_healthy = False
    except Exception as e:
        checks["rabbitmq"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Check Redis
    try:
        import redis.asyncio as aioredis

        from urgp.config import get_settings

        settings = get_settings()
        shared_redis = getattr(request.app.state, "redis", None)
        if shared_redis is not None:
            await shared_redis.ping()
        else:
            redis_factory = cast(Any, aioredis.from_url)
            redis_client = redis_factory(str(settings.redis_url), socket_timeout=5)
            await redis_client.ping()
            aclose = getattr(redis_client, "aclose", None)
            if callable(aclose):
                await aclose()
            else:
                await redis_client.close()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    if not all_healthy:
        response.status_code = 503

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "service": "urgp-api",
        "checks": checks,
        "response_time_ms": elapsed_ms,
    }
