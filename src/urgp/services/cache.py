"""Redis caching layer for external API responses.

Provides a typed interface over Redis with JSON serialization,
configurable TTL, and graceful degradation when Redis is unavailable.

Reference: docs/04-requirements.md R12.7, R13.7 (5-minute cache TTL)
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Re-export the Redis type for type annotations
try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]


class CacheService:
    """Thin wrapper over Redis for JSON-based caching with graceful degradation.

    If Redis is unavailable, all operations silently return None / no-op.
    """

    def __init__(self, redis_client: Any | None, *, default_ttl: int = 300) -> None:
        """Initialize cache service.

        Args:
            redis_client: An initialized redis.asyncio.Redis instance, or None to disable caching.
            default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes).
        """
        self._redis = redis_client
        self._default_ttl = default_ttl

    @property
    def available(self) -> bool:
        """Check if Redis client is available."""
        return self._redis is not None

    async def get_json(self, key: str) -> Any | None:
        """Get a cached JSON value by key.

        Returns:
            Deserialized JSON value, or None if not found or Redis unavailable.
        """
        if self._redis is None:
            return None

        try:
            raw = await self._redis.get(f"cache:{key}")
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("Cache read failed for key '%s'", key, exc_info=True)
            return None

    async def set_json(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        """Set a JSON value in cache with TTL.

        Args:
            key: Cache key (will be prefixed with 'cache:')
            value: JSON-serializable value
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        if self._redis is None:
            return

        try:
            ttl_seconds = ttl if ttl is not None else self._default_ttl
            serialized = json.dumps(value, default=str)
            await self._redis.set(f"cache:{key}", serialized, ex=ttl_seconds)
        except Exception:
            logger.debug("Cache write failed for key '%s'", key, exc_info=True)

    async def delete(self, key: str) -> None:
        """Delete a cached value by key."""
        if self._redis is None:
            return

        try:
            await self._redis.delete(f"cache:{key}")
        except Exception:
            logger.debug("Cache delete failed for key '%s'", key, exc_info=True)

    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns number of keys deleted."""
        if self._redis is None:
            return 0

        try:
            cursor: int = 0
            deleted = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=f"cache:{pattern}", count=100)
                if keys:
                    await self._redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            return deleted
        except Exception:
            logger.debug("Cache flush failed for pattern '%s'", pattern, exc_info=True)
            return 0


__all__ = [
    "CacheService",
]
