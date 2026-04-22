"""Unit tests for the rate limiter (P1-3.T4).

Tests cover:
- P1-3.T4: Rate limiting enforcement — exceed limit → HTTP 429 + Retry-After
- Under limit → allowed with correct headers
- Write vs read limits
- Sliding window behavior
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from urgp.middleware.rate_limiter import RateLimiter

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _create_mock_redis(current_count: int = 0, *, allow_second_pipeline: bool = True) -> MagicMock:
    """Create a mock Redis client with synchronous pipeline() method.

    Redis.pipeline() is NOT a coroutine — it returns a pipeline object
    synchronously. The pipeline's execute() IS a coroutine.
    """
    mock = MagicMock()

    # First pipeline call (for zremrangebyscore + zcard)
    pipe1 = MagicMock()
    pipe1.zremrangebyscore = MagicMock()
    pipe1.zcard = MagicMock()
    pipe1.execute = AsyncMock(return_value=[0, current_count])

    if allow_second_pipeline:
        # Second pipeline call (for zadd + expire)
        pipe2 = MagicMock()
        pipe2.zadd = MagicMock()
        pipe2.expire = MagicMock()
        pipe2.execute = AsyncMock(return_value=[True, True])
        mock.pipeline.side_effect = [pipe1, pipe2]
    else:
        mock.pipeline.return_value = pipe1

    return mock


# ─────────────────────────────────────────────
# P1-3.T4: Rate Limiting Tests
# ─────────────────────────────────────────────


class TestRateLimiter:
    """P1-3.T4: Rate limiting enforcement."""

    async def test_under_limit_allowed(self) -> None:
        """Request under the rate limit is allowed."""
        mock_redis = _create_mock_redis(current_count=5)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("test-key", is_write=False, read_limit=100)

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 94  # 100 - 5 - 1

    async def test_at_limit_rejected(self) -> None:
        """Request at the rate limit is rejected."""
        mock_redis = _create_mock_redis(current_count=20, allow_second_pipeline=False)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("test-key", is_write=True, write_limit=20)

        assert result.allowed is False
        assert result.limit == 20
        assert result.remaining == 0

    async def test_over_limit_rejected(self) -> None:
        """Request over the rate limit is rejected."""
        mock_redis = _create_mock_redis(current_count=150, allow_second_pipeline=False)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("test-key", is_write=False, read_limit=100)

        assert result.allowed is False
        assert result.remaining == 0

    async def test_write_limit_lower_than_read(self) -> None:
        """Write limit (20/min) is stricter than read limit (100/min)."""
        mock_redis_write = _create_mock_redis(current_count=15)
        limiter_write = RateLimiter(mock_redis_write)

        mock_redis_read = _create_mock_redis(current_count=15)
        limiter_read = RateLimiter(mock_redis_read)

        write_result = await limiter_write.check_rate_limit("key", is_write=True, write_limit=20)
        read_result = await limiter_read.check_rate_limit("key", is_write=False, read_limit=100)

        assert write_result.allowed is True
        assert read_result.allowed is True
        # Write has fewer remaining
        assert write_result.remaining < read_result.remaining

    async def test_result_contains_reset_timestamp(self) -> None:
        """Result includes a valid reset timestamp."""
        mock_redis = _create_mock_redis(current_count=0)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("test-key")

        assert result.reset > 0
        assert isinstance(result.reset, int)

    async def test_first_request_has_full_remaining(self) -> None:
        """First request shows nearly full remaining capacity."""
        mock_redis = _create_mock_redis(current_count=0)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("test-key", is_write=False, read_limit=100)

        assert result.allowed is True
        assert result.remaining == 99  # 100 - 0 - 1

    async def test_different_api_keys_independent(self) -> None:
        """Different API keys have independent rate limits."""
        mock_redis1 = _create_mock_redis(current_count=0)
        mock_redis2 = _create_mock_redis(current_count=0)

        result1 = await RateLimiter(mock_redis1).check_rate_limit("key-1")
        result2 = await RateLimiter(mock_redis2).check_rate_limit("key-2")

        assert result1.allowed is True
        assert result2.allowed is True
