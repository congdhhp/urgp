"""Rate limiting middleware support — Redis-backed sliding window counter.

Implements per-API-key rate limiting using a Redis Lua script so each
check-and-record operation is atomic under concurrency.

Reference: docs/07-implementation-plan.md § P1-3.6
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    RedisType = aioredis.Redis[Any]
else:
    RedisType = aioredis.Redis

_KEY_PREFIX = "ratelimit"
_WINDOW_SECONDS = 60

_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local member = ARGV[5]

redis.call("ZREMRANGEBYSCORE", key, "-inf", window_start)

local current = redis.call("ZCARD", key)
if current >= limit then
  redis.call("EXPIRE", key, ttl)
  return {0, limit, 0}
end

redis.call("ZADD", key, now, member)
redis.call("EXPIRE", key, ttl)

local remaining = limit - current - 1
return {1, limit, remaining}
"""


def _fingerprint_api_key(api_key: str) -> str:
    """Return a non-reversible fingerprint for logging."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset: int

    def as_headers(self) -> dict[str, str]:
        """Render the result as HTTP response headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset),
        }


class RateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, redis_client: RedisType) -> None:
        self._redis = redis_client

    async def _eval_script(self, script: str, *args: str) -> Any:
        eval_fn = cast(Any, self._redis.eval)
        return await eval_fn(script, 1, *args)

    async def check_rate_limit(
        self,
        api_key: str,
        *,
        is_write: bool = False,
        read_limit: int = 100,
        write_limit: int = 20,
    ) -> RateLimitResult:
        """Check and update the rate limit for an API key atomically."""
        limit = write_limit if is_write else read_limit
        operation = "write" if is_write else "read"
        key = f"{_KEY_PREFIX}:{api_key}:{operation}"

        now = time.time()
        window_start = now - _WINDOW_SECONDS
        reset_at = int(now) + _WINDOW_SECONDS
        member = f"{now}:{uuid.uuid4().hex}"

        raw_result = await self._eval_script(
            _SLIDING_WINDOW_SCRIPT,
            key,
            str(now),
            str(window_start),
            str(limit),
            str(_WINDOW_SECONDS + 1),
            member,
        )

        result = list(raw_result)
        allowed = bool(int(result[0]))
        resolved_limit = int(result[1])
        remaining = int(result[2])

        if not allowed:
            logger.warning(
                "Rate limit exceeded [api_key=%s, operation=%s, limit=%d]",
                _fingerprint_api_key(api_key),
                operation,
                resolved_limit,
            )

        return RateLimitResult(
            allowed=allowed,
            limit=resolved_limit,
            remaining=remaining,
            reset=reset_at,
        )
