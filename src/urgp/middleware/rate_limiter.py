"""Rate limiting middleware — Redis sliding window counter.

Implements per-API-key rate limiting using Redis sorted sets.
Configurable limits for read (100/min) and write (20/min) operations.

Reference: docs/07-implementation-plan.md § P1-3.6
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Key prefix for rate limit entries
_KEY_PREFIX = "ratelimit"

# Sliding window duration in seconds
_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is within the rate limit.
        limit: Maximum requests allowed in the window.
        remaining: Requests remaining in the current window.
        reset: Unix timestamp when the window resets.
    """

    allowed: bool
    limit: int
    remaining: int
    reset: int


class RateLimiter:
    """Redis-backed sliding window rate limiter.

    Uses Redis sorted sets with timestamp-based scores to implement
    an accurate sliding window counter per API key.

    Algorithm:
        1. Remove expired entries (older than window)
        2. Count remaining entries in the window
        3. If under limit, add current timestamp
        4. Return result with remaining capacity
    """

    def __init__(self, redis_client: aioredis.Redis[bytes]) -> None:
        """Initialize with a Redis client.

        Args:
            redis_client: Async Redis client instance.
        """
        self._redis = redis_client

    async def check_rate_limit(
        self,
        api_key: str,
        *,
        is_write: bool = False,
        read_limit: int = 100,
        write_limit: int = 20,
    ) -> RateLimitResult:
        """Check and update the rate limit for an API key.

        Uses a Redis sorted set pipeline:
        1. ZREMRANGEBYSCORE — remove entries outside the window
        2. ZCARD — count current entries
        3. ZADD — add current request (if allowed)
        4. EXPIRE — set TTL on the key

        Args:
            api_key: The API key to rate-limit.
            is_write: True for write operations (lower limit).
            read_limit: Max read requests per minute.
            write_limit: Max write requests per minute.

        Returns:
            RateLimitResult with allowed flag and header values.
        """
        limit = write_limit if is_write else read_limit
        operation = "write" if is_write else "read"
        key = f"{_KEY_PREFIX}:{api_key}:{operation}"

        now = time.time()
        window_start = now - _WINDOW_SECONDS
        reset_at = int(now) + _WINDOW_SECONDS

        # Execute atomically via pipeline
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        results = await pipe.execute()

        current_count: int = results[1]

        if current_count >= limit:
            # Rate limit exceeded
            remaining = 0
            logger.warning(
                "Rate limit exceeded [key=%s, operation=%s, count=%d, limit=%d]",
                api_key[:8] + "...",
                operation,
                current_count,
                limit,
            )
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=remaining,
                reset=reset_at,
            )

        # Under limit — record this request
        pipe2 = self._redis.pipeline()
        pipe2.zadd(key, {f"{now}": now})
        pipe2.expire(key, _WINDOW_SECONDS + 1)
        await pipe2.execute()

        remaining = max(0, limit - current_count - 1)

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset=reset_at,
        )
