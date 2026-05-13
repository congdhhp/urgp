"""Unit tests for notification rendering and retry semantics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from urgp.models.enums import (
    BuildStatus,
    BuildType,
    NotificationChannel,
    NotificationEventType,
)
from urgp.models.manifest import BuildManifest
from urgp.models.notification import NotificationSubscription
from urgp.models.product import Product, Release
from urgp.models.traceability import Commit, Issue, PullRequest
from urgp.schemas.notifications import NotificationRequest
from urgp.services.notification_processing import NotificationRenderer, RetryPolicy


def _manifest() -> BuildManifest:
    product = Product(external_id="S32_IDE", name="S32 Design Studio")
    release = Release(product=product, version="3.6.8-RFP", status="active")
    pull_request = PullRequest(external_id="456", repository="bitbucket.org/nxp/s32", title="Fix traceability")
    issue = Issue(external_id="PROJ-1234", tracker_type="jira", title="Investigate release flow")
    commit = Commit(
        repository="bitbucket.org/nxp/s32",
        hash="a" * 40,
        pull_requests=[pull_request],
        issues=[issue],
    )
    return BuildManifest(
        id=uuid.uuid4(),
        build_id="260330",
        product=product,
        release=release,
        build_type=BuildType.NIGHTLY,
        status=BuildStatus.COMPLETED,
        traceability_incomplete=False,
        commits=[commit],
        artifacts=[],
        notifications=[],
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _subscription(channel: NotificationChannel) -> NotificationSubscription:
    kwargs: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": "qa@example.com",
        "product_id": uuid.uuid4(),
        "channel": channel,
        "active": True,
    }
    if channel == NotificationChannel.WEBHOOK:
        kwargs["webhook_url"] = "https://hooks.example.test/urgp"
    return NotificationSubscription(**kwargs)


class TestNotificationRenderer:
    def test_renderer_builds_clean_webhook_payload(self) -> None:
        renderer = NotificationRenderer(SimpleNamespace(portal_base_url="http://localhost:8000/portal"))
        manifest = _manifest()
        subscription = _subscription(NotificationChannel.WEBHOOK)
        request = NotificationRequest(
            manifest_id=manifest.id,
            build_id=manifest.build_id,
            product_id=manifest.product.external_id,
            event_type=NotificationEventType.BUILD_COMPLETED,
            triggered_at=datetime.now(tz=UTC),
            trigger_source="hydration_worker",
        )

        rendered = renderer.render(manifest, subscription, request)

        assert rendered.destination == "https://hooks.example.test/urgp"
        assert rendered.payload["schema_version"] == "v1"
        assert rendered.payload["event_type"] == "build_completed"
        assert "links" in rendered.payload
        assert "_webhook_url" not in rendered.payload


class TestRetryPolicy:
    @pytest.mark.asyncio
    async def test_retry_policy_retries_then_succeeds(self) -> None:
        policy = RetryPolicy(max_retries=2, base_backoff_seconds=0.0)
        attempts = 0

        async def flaky_send() -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                msg = "temporary failure"
                raise RuntimeError(msg)

        outcome = await policy.execute(flaky_send)

        assert attempts == 3
        assert outcome.status == "sent"
        assert outcome.attempt_count == 3
        assert outcome.sent_at is not None

    @pytest.mark.asyncio
    async def test_retry_policy_surfaces_final_failure(self) -> None:
        policy = RetryPolicy(max_retries=1, base_backoff_seconds=0.0)
        attempts = 0

        async def always_fail() -> None:
            nonlocal attempts
            attempts += 1
            msg = "smtp down"
            raise RuntimeError(msg)

        outcome = await policy.execute(always_fail)

        assert attempts == 2
        assert outcome.status == "failed"
        assert outcome.attempt_count == 2
        assert outcome.last_error == "smtp down"
