"""FastAPI dependency injection for the Event Gateway."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, cast

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from urgp.middleware.api_key_auth import APIKeyDep
from urgp.middleware.rate_limiter import RateLimiter
from urgp.schemas.responses import RateLimitExceededResponse
from urgp.services.idempotency import IdempotencyService
from urgp.services.publisher import EventPublisher

if TYPE_CHECKING:
    RedisType = aioredis.Redis[Any]
else:
    RedisType = aioredis.Redis


def _service_unavailable(message: str, *, error: str = "service_unavailable") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": error,
            "message": message,
        },
    )


def _get_rate_limit_headers(limit: int, remaining: int, reset: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset),
    }


def _store_rate_limit_headers(request: Request, headers: dict[str, str]) -> None:
    request.state.rate_limit_headers = headers


async def get_redis(request: Request) -> RedisType:
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        raise _service_unavailable(
            "Redis is unavailable. Rate limiting and idempotency checks cannot be performed.",
        )
    return cast(RedisType, redis_client)


async def get_publisher(request: Request) -> EventPublisher:
    publisher = getattr(request.app.state, "publisher", None)
    if publisher is None or not publisher.is_connected:
        raise _service_unavailable(
            "RabbitMQ publisher is unavailable. Event ingestion is temporarily disabled.",
            error="broker_unavailable",
        )
    return cast(EventPublisher, publisher)


async def get_idempotency_service(
    redis_client: Annotated[RedisType, Depends(get_redis)],
) -> IdempotencyService:
    from urgp.config import get_settings

    settings = get_settings()
    return IdempotencyService(
        redis_client,
        completed_ttl_seconds=settings.idempotency_ttl_seconds,
        pending_ttl_seconds=settings.idempotency_pending_ttl_seconds,
    )


async def _enforce_rate_limit(request: Request, api_key: str, *, is_write: bool) -> None:
    from urgp.config import get_settings

    settings = get_settings()
    redis_client = await get_redis(request)
    rate_limiter = RateLimiter(redis_client)
    rate_result = await rate_limiter.check_rate_limit(
        api_key,
        is_write=is_write,
        read_limit=settings.rate_limit_read,
        write_limit=settings.rate_limit_write,
    )

    headers = _get_rate_limit_headers(
        rate_result.limit,
        rate_result.remaining,
        rate_result.reset,
    )
    _store_rate_limit_headers(request, headers)

    if rate_result.allowed:
        return

    retry_after = max(1, rate_result.reset - int(datetime.now(tz=UTC).timestamp()))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=RateLimitExceededResponse(
            limit=rate_result.limit,
            remaining=0,
            reset_at=rate_result.reset,
        ).model_dump(),
        headers={
            **headers,
            "Retry-After": str(retry_after),
        },
    )


async def require_write_access(request: Request, api_key: APIKeyDep) -> str:
    await _enforce_rate_limit(request, api_key, is_write=True)
    return api_key


async def require_read_access(request: Request, api_key: APIKeyDep) -> str:
    await _enforce_rate_limit(request, api_key, is_write=False)
    return api_key


RedisDep = Annotated[RedisType, Depends(get_redis)]
PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]
IdempotencyDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]
WriteAccessDep = Annotated[str, Depends(require_write_access)]
ReadAccessDep = Annotated[str, Depends(require_read_access)]

__all__ = [
    "IdempotencyDep",
    "PublisherDep",
    "ReadAccessDep",
    "RedisDep",
    "WriteAccessDep",
    "get_idempotency_service",
    "get_publisher",
    "get_redis",
    "require_read_access",
    "require_write_access",
]
