"""Unit tests for the idempotency service (P1-3.T3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fakes import FakeRedis
from urgp.services.idempotency import IdempotencyService


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def service(fake_redis: FakeRedis) -> IdempotencyService:
    return IdempotencyService(
        fake_redis,
        completed_ttl_seconds=86400,
        pending_ttl_seconds=120,
    )


class TestIdempotencyService:
    """P1-3.T3: Idempotency — same build_id twice → second returns duplicate."""

    async def test_first_submission_creates_reservation(self, service: IdempotencyService) -> None:
        result = await service.begin_processing("build-001", "product-A")

        assert result.status == "started"
        assert result.reservation_token is not None
        assert result.pending_since is not None

    async def test_duplicate_detected_after_completion(self, service: IdempotencyService) -> None:
        first = await service.begin_processing("build-001", "product-A")
        ingestion_timestamp = datetime.now(tz=UTC)

        completed = await service.mark_completed(
            "build-001",
            "product-A",
            first.reservation_token or "",
            ingestion_timestamp=ingestion_timestamp,
        )
        duplicate = await service.begin_processing("build-001", "product-A")

        assert completed is True
        assert duplicate.status == "duplicate"
        assert duplicate.original_timestamp == ingestion_timestamp

    async def test_in_progress_is_reported_while_reservation_exists(self, service: IdempotencyService) -> None:
        await service.begin_processing("build-001", "product-A")

        duplicate = await service.begin_processing("build-001", "product-A")

        assert duplicate.status == "in_progress"
        assert duplicate.pending_since is not None

    async def test_release_reservation_allows_retry(self, service: IdempotencyService) -> None:
        first = await service.begin_processing("build-001", "product-A")
        released = await service.release_reservation(
            "build-001",
            "product-A",
            first.reservation_token or "",
        )
        second = await service.begin_processing("build-001", "product-A")

        assert released is True
        assert second.status == "started"

    async def test_get_status_only_returns_completed_timestamp(self, service: IdempotencyService) -> None:
        first = await service.begin_processing("build-001", "product-A")
        assert await service.get_status("build-001", "product-A") is None

        original_timestamp = datetime.now(tz=UTC)
        await service.mark_completed(
            "build-001",
            "product-A",
            first.reservation_token or "",
            ingestion_timestamp=original_timestamp,
        )

        assert await service.get_status("build-001", "product-A") == original_timestamp

    async def test_mark_completed_rejects_wrong_token(self, service: IdempotencyService) -> None:
        await service.begin_processing("build-001", "product-A")

        completed = await service.mark_completed(
            "build-001",
            "product-A",
            "wrong-token",
            ingestion_timestamp=datetime.now(tz=UTC),
        )

        assert completed is False
