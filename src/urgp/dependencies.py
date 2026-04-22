"""FastAPI dependency injection for the Event Gateway.

Provides shared dependencies (Redis, RabbitMQ publisher, services)
to API route handlers via FastAPI's Depends() mechanism.
"""

from __future__ import annotations

from typing import Annotated, Any

import redis.asyncio as aioredis
from fastapi import Depends, Request

from urgp.middleware.rate_limiter import RateLimiter
from urgp.services.idempotency import IdempotencyService
from urgp.services.publisher import EventPublisher


def _get_app_state(request: Request) -> Any:
    """Extract application state from the request."""
    return request.app.state


async def get_redis(request: Request) -> aioredis.Redis:  # type: ignore[type-arg]
    """Get the shared Redis client from app state.

    Args:
        request: The incoming request (injected by FastAPI).

    Returns:
        Async Redis client.
    """
    return request.app.state.redis  # type: ignore[no-any-return]


async def get_publisher(request: Request) -> EventPublisher:
    """Get the shared EventPublisher from app state.

    Args:
        request: The incoming request (injected by FastAPI).

    Returns:
        EventPublisher instance.
    """
    return request.app.state.publisher  # type: ignore[no-any-return]


async def get_idempotency_service(
    redis_client: Annotated[Any, Depends(get_redis)],
) -> IdempotencyService:
    """Construct an IdempotencyService with the shared Redis client.

    Args:
        redis_client: Injected Redis client.

    Returns:
        IdempotencyService instance.
    """
    return IdempotencyService(redis_client)


async def get_rate_limiter(
    redis_client: Annotated[Any, Depends(get_redis)],
) -> RateLimiter:
    """Construct a RateLimiter with the shared Redis client.

    Args:
        redis_client: Injected Redis client.

    Returns:
        RateLimiter instance.
    """
    return RateLimiter(redis_client)


# ─────────────────────────────────────────────
# Type aliases for cleaner route signatures
# ─────────────────────────────────────────────

RedisDep = Annotated[Any, Depends(get_redis)]
PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]
IdempotencyDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
