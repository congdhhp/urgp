"""Idempotency service — Redis-backed duplicate detection.

Prevents reprocessing the same build event by checking a Redis key
composed of `build_id + product_id` with a 24-hour TTL.

Uses Redis SET NX EX for atomic check-and-mark operations.

Reference: docs/07-implementation-plan.md § P1-3.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Key prefix for idempotency entries
_KEY_PREFIX = "idempotency"

# TTL for idempotency keys: 24 hours
_TTL_SECONDS = 86400


@dataclass(frozen=True)
class IdempotencyResult:
    """Result of an idempotency check.

    Attributes:
        is_duplicate: True if this build_id+product_id was already processed.
        original_timestamp: Timestamp of the original ingestion (if duplicate).
    """

    is_duplicate: bool
    original_timestamp: datetime | None = None


def _make_key(product_id: str, build_id: str) -> str:
    """Build the Redis key for an idempotency entry.

    Args:
        product_id: The product identifier.
        build_id: The build identifier.

    Returns:
        Redis key string.
    """
    return f"{_KEY_PREFIX}:{product_id}:{build_id}"


class IdempotencyService:
    """Redis-backed idempotency check for build ingestion.

    Ensures each `build_id + product_id` combination is processed
    at most once within a 24-hour window.
    """

    def __init__(self, redis_client: aioredis.Redis[bytes]) -> None:
        """Initialize with a Redis client.

        Args:
            redis_client: Async Redis client instance.
        """
        self._redis = redis_client

    async def check_and_mark(self, build_id: str, product_id: str) -> IdempotencyResult:
        """Atomically check for duplicate and mark as processed.

        Uses Redis SET NX EX for an atomic set-if-not-exists with expiry.

        Args:
            build_id: The build identifier from the payload.
            product_id: The product identifier from the payload.

        Returns:
            IdempotencyResult with is_duplicate flag and original timestamp.
        """
        key = _make_key(product_id, build_id)
        now = datetime.now(tz=UTC)
        timestamp_str = now.isoformat()

        # SET NX EX: set key only if it doesn't exist, with TTL
        was_set = await self._redis.set(key, timestamp_str, nx=True, ex=_TTL_SECONDS)

        if was_set:
            # First time seeing this build — not a duplicate
            logger.info(
                "Idempotency: new build event [product=%s, build=%s]",
                product_id,
                build_id,
            )
            return IdempotencyResult(is_duplicate=False)

        # Key already exists — this is a duplicate
        existing_value = await self._redis.get(key)
        original_timestamp = None
        if existing_value:
            try:
                original_timestamp = datetime.fromisoformat(
                    existing_value.decode() if isinstance(existing_value, bytes) else existing_value
                )
            except (ValueError, AttributeError):
                logger.warning("Could not parse original timestamp for key %s", key)

        logger.info(
            "Idempotency: duplicate build event [product=%s, build=%s]",
            product_id,
            build_id,
        )
        return IdempotencyResult(is_duplicate=True, original_timestamp=original_timestamp)

    async def get_status(self, build_id: str, product_id: str) -> datetime | None:
        """Check if a build event was already processed.

        Args:
            build_id: The build identifier.
            product_id: The product identifier.

        Returns:
            Original ingestion timestamp if found, None otherwise.
        """
        key = _make_key(product_id, build_id)
        value = await self._redis.get(key)
        if value:
            try:
                return datetime.fromisoformat(value.decode() if isinstance(value, bytes) else value)
            except (ValueError, AttributeError):
                return None
        return None
