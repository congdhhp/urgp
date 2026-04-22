"""Unit tests for the rate limiter (P1-3.T4)."""

from __future__ import annotations

from unittest.mock import patch

from tests.unit.fakes import FakeRedis
from urgp.middleware.rate_limiter import RateLimiter


class TestRateLimiter:
    """P1-3.T4: Rate limiting enforcement."""

    async def test_under_limit_allowed(self) -> None:
        limiter = RateLimiter(FakeRedis())

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1000.0):
            result = await limiter.check_rate_limit("test-key", is_write=False, read_limit=100)

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 99
        assert result.reset == 1060

    async def test_at_limit_rejected(self) -> None:
        redis = FakeRedis()
        limiter = RateLimiter(redis)

        for current_time in range(1000, 1020):
            with patch("urgp.middleware.rate_limiter.time.time", return_value=float(current_time)):
                await limiter.check_rate_limit("test-key", is_write=True, write_limit=20)

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1020.0):
            result = await limiter.check_rate_limit("test-key", is_write=True, write_limit=20)

        assert result.allowed is False
        assert result.limit == 20
        assert result.remaining == 0

    async def test_write_limit_lower_than_read(self) -> None:
        redis = FakeRedis()
        limiter = RateLimiter(redis)

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1000.0):
            write_result = await limiter.check_rate_limit("key", is_write=True, write_limit=20)

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1001.0):
            read_result = await limiter.check_rate_limit("key", is_write=False, read_limit=100)

        assert write_result.allowed is True
        assert read_result.allowed is True
        assert write_result.remaining < read_result.remaining

    async def test_sliding_window_expires_old_entries(self) -> None:
        redis = FakeRedis()
        limiter = RateLimiter(redis)

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1000.0):
            await limiter.check_rate_limit("key", read_limit=1)

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1061.0):
            result = await limiter.check_rate_limit("key", read_limit=1)

        assert result.allowed is True
        assert result.remaining == 0

    async def test_result_contains_headers_ready_values(self) -> None:
        limiter = RateLimiter(FakeRedis())

        with patch("urgp.middleware.rate_limiter.time.time", return_value=1234.0):
            result = await limiter.check_rate_limit("test-key")

        assert result.as_headers() == {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "99",
            "X-RateLimit-Reset": "1294",
        }
