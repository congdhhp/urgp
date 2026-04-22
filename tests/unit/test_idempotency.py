"""Unit tests for the idempotency service (P1-3.T3).

Tests cover:
- P1-3.T3: Same build_id twice → second returns 200, no duplicate processing
- First submission is accepted
- Duplicate detection returns original timestamp
- Different build_ids are independent
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from urgp.services.idempotency import IdempotencyService

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return AsyncMock()


@pytest.fixture
def service(mock_redis):
    """Create an IdempotencyService with mock Redis."""
    return IdempotencyService(mock_redis)


# ─────────────────────────────────────────────
# P1-3.T3: Idempotency Tests
# ─────────────────────────────────────────────


class TestIdempotencyService:
    """P1-3.T3: Idempotency — same build_id twice → second returns duplicate."""

    async def test_first_submission_accepted(self, service, mock_redis) -> None:
        """First submission of a build_id is accepted (not duplicate)."""
        mock_redis.set = AsyncMock(return_value=True)  # NX succeeded → key was new

        result = await service.check_and_mark("build-001", "product-A")

        assert result.is_duplicate is False
        assert result.original_timestamp is None
        mock_redis.set.assert_called_once()

    async def test_duplicate_detected(self, service, mock_redis) -> None:
        """Second submission of same build_id + product_id returns duplicate."""
        original_ts = datetime.now(tz=UTC).isoformat()
        mock_redis.set = AsyncMock(return_value=False)  # NX failed → key existed
        mock_redis.get = AsyncMock(return_value=original_ts.encode())

        result = await service.check_and_mark("build-001", "product-A")

        assert result.is_duplicate is True
        assert result.original_timestamp is not None

    async def test_different_build_ids_are_independent(self, service, mock_redis) -> None:
        """Different build_ids are not treated as duplicates."""
        mock_redis.set = AsyncMock(return_value=True)  # Always new

        result1 = await service.check_and_mark("build-001", "product-A")
        result2 = await service.check_and_mark("build-002", "product-A")

        assert result1.is_duplicate is False
        assert result2.is_duplicate is False

    async def test_same_build_id_different_products(self, service, mock_redis) -> None:
        """Same build_id but different product_id is not a duplicate."""
        mock_redis.set = AsyncMock(return_value=True)

        result1 = await service.check_and_mark("build-001", "product-A")
        result2 = await service.check_and_mark("build-001", "product-B")

        assert result1.is_duplicate is False
        assert result2.is_duplicate is False

    async def test_redis_key_format(self, service, mock_redis) -> None:
        """Verify the Redis key follows the expected format."""
        mock_redis.set = AsyncMock(return_value=True)

        await service.check_and_mark("build-001", "product-A")

        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert key == "idempotency:product-A:build-001"

    async def test_redis_key_has_24h_ttl(self, service, mock_redis) -> None:
        """Verify the Redis key is set with 24-hour TTL."""
        mock_redis.set = AsyncMock(return_value=True)

        await service.check_and_mark("build-001", "product-A")

        call_kwargs = mock_redis.set.call_args[1]
        assert call_kwargs["ex"] == 86400  # 24 hours
        assert call_kwargs["nx"] is True

    async def test_get_status_exists(self, service, mock_redis) -> None:
        """get_status returns timestamp for existing entry."""
        ts = datetime.now(tz=UTC).isoformat()
        mock_redis.get = AsyncMock(return_value=ts.encode())

        result = await service.get_status("build-001", "product-A")

        assert result is not None

    async def test_get_status_not_exists(self, service, mock_redis) -> None:
        """get_status returns None for non-existing entry."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await service.get_status("build-999", "product-A")

        assert result is None

    async def test_duplicate_with_unparseable_timestamp(self, service, mock_redis) -> None:
        """Gracefully handle unparseable timestamps in Redis."""
        mock_redis.set = AsyncMock(return_value=False)
        mock_redis.get = AsyncMock(return_value=b"not-a-timestamp")

        result = await service.check_and_mark("build-001", "product-A")

        assert result.is_duplicate is True
        assert result.original_timestamp is None  # Graceful fallback
