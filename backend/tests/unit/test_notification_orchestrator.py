"""Integration tests for NotificationOrchestrator.process_request().

These tests exercise the full orchestration flow — subscription matching,
rendering, transport dispatch (via fakes), retry policy, and delivery
status persistence — using mock transports and in-memory data fixtures.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from urgp.models.enums import (
    BuildStatus,
    BuildType,
    NotificationChannel,
    NotificationEventType,
)
from urgp.models.manifest import BuildManifest
from urgp.models.notification import Notification, NotificationSubscription
from urgp.models.product import Product, Release
from urgp.models.traceability import Commit, Issue, PullRequest
from urgp.schemas.notifications import NotificationRequest
from urgp.services.notification_processing import (
    NotificationOrchestrator,
    NotificationRenderer,
    RenderedNotification,
    RetryPolicy,
)

# ─────────────────────────────────────────────
# Fixtures & Helpers
# ─────────────────────────────────────────────

_PRODUCT_ID = uuid.uuid4()
_RELEASE_ID = uuid.uuid4()
_MANIFEST_ID = uuid.uuid4()
_SUB_EMAIL_ID = uuid.uuid4()
_SUB_WEBHOOK_ID = uuid.uuid4()


def _build_manifest() -> BuildManifest:
    """Minimal manifest with loaded relationships for renderer."""
    product = Product(id=_PRODUCT_ID, external_id="S32_IDE", name="S32 Design Studio")
    release = Release(id=_RELEASE_ID, product=product, product_id=_PRODUCT_ID, version="3.6.8-RFP", status="active")
    pull_request = PullRequest(external_id="456", repository="bitbucket.org/nxp/s32", title="Fix traceability")
    issue = Issue(external_id="PROJ-1234", tracker_type="jira", title="Investigate release flow")
    commit = Commit(
        repository="bitbucket.org/nxp/s32",
        hash="a" * 40,
        pull_requests=[pull_request],
        issues=[issue],
    )
    manifest = BuildManifest(
        id=_MANIFEST_ID,
        build_id="260330",
        product_id=_PRODUCT_ID,
        product=product,
        release_id=_RELEASE_ID,
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
    return manifest


def _email_subscription() -> NotificationSubscription:
    product = Product(id=_PRODUCT_ID, external_id="S32_IDE", name="S32 Design Studio")
    return NotificationSubscription(
        id=_SUB_EMAIL_ID,
        user_id="qa@example.com",
        product_id=_PRODUCT_ID,
        product=product,
        release_id=None,
        release=None,
        channel=NotificationChannel.EMAIL,
        webhook_url=None,
        active=True,
    )


def _webhook_subscription() -> NotificationSubscription:
    product = Product(id=_PRODUCT_ID, external_id="S32_IDE", name="S32 Design Studio")
    return NotificationSubscription(
        id=_SUB_WEBHOOK_ID,
        user_id="webhook-user",
        product_id=_PRODUCT_ID,
        product=product,
        release_id=None,
        release=None,
        channel=NotificationChannel.WEBHOOK,
        webhook_url="https://hooks.example.test/urgp",
        active=True,
    )


def _notification_request() -> NotificationRequest:
    return NotificationRequest(
        manifest_id=_MANIFEST_ID,
        build_id="260330",
        product_id="S32_IDE",
        event_type=NotificationEventType.BUILD_COMPLETED,
        triggered_at=datetime.now(tz=UTC),
        trigger_source="hydration_worker",
    )


class _FakeSessionContext:
    """Mimics an AsyncSession with predictable subscription and notification data."""

    def __init__(
        self,
        manifest: BuildManifest,
        subscriptions: list[NotificationSubscription],
    ) -> None:
        self._manifest = manifest
        self._subscriptions = subscriptions
        self._notifications: dict[uuid.UUID, Notification] = {}
        self._flush_counter = 0

    async def scalars(self, statement: Any) -> Any:
        """Return matching subscriptions for any select query."""

        class _Result:
            def __init__(self, items: list[Any]) -> None:
                self._items = items

            def all(self) -> list[Any]:
                return self._items

        return _Result(self._subscriptions)

    async def scalar(self, statement: Any) -> Any:
        """Return manifest for load queries, None for notification existence checks."""
        return None

    async def get(self, model: type, id: uuid.UUID) -> Notification | None:
        return self._notifications.get(id)

    def add(self, record: Any) -> None:
        if isinstance(record, Notification):
            if record.id is None:
                record.id = uuid.uuid4()
            self._notifications[record.id] = record

    async def flush(self) -> None:
        self._flush_counter += 1
        for record in self._notifications.values():
            if record.id is None:
                record.id = uuid.uuid4()

    async def commit(self) -> None:
        pass

    async def __aenter__(self) -> _FakeSessionContext:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class _FakeSessionFactory:
    """Returns the fake session context on each call."""

    def __init__(self, session: _FakeSessionContext) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        return self._session


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────


class TestNotificationOrchestrator:
    """Integration tests for the full orchestration flow."""

    @pytest.mark.asyncio
    async def test_process_request_dispatches_to_both_transports(self) -> None:
        """A request with one email and one webhook subscription should invoke both transports."""
        manifest = _build_manifest()
        subscriptions = [_email_subscription(), _webhook_subscription()]
        request = _notification_request()

        fake_session = _FakeSessionContext(manifest, subscriptions)
        fake_factory = _FakeSessionFactory(fake_session)

        email_transport = MagicMock()
        email_transport.send = AsyncMock(return_value=None)
        webhook_transport = MagicMock()
        webhook_transport.send = AsyncMock(return_value=None)

        settings = SimpleNamespace(
            portal_base_url="http://localhost:8000/portal",
            notification_max_retries=0,
            notification_retry_backoff_seconds=0.0,
        )

        orchestrator = NotificationOrchestrator(
            session_factory_provider=lambda: fake_factory,
            settings=settings,  # type: ignore[arg-type]
            renderer=NotificationRenderer(settings),  # type: ignore[arg-type]
            retry_policy=RetryPolicy(max_retries=0, base_backoff_seconds=0.0),
            transports={
                NotificationChannel.EMAIL: email_transport,
                NotificationChannel.WEBHOOK: webhook_transport,
            },
        )

        # Override _load_manifest to return our in-memory manifest
        orchestrator._load_manifest = AsyncMock(return_value=manifest)  # type: ignore[method-assign]

        await orchestrator.process_request(request)

        email_transport.send.assert_awaited_once()
        webhook_transport.send.assert_awaited_once()

        # Verify rendered content was correct
        email_call = email_transport.send.await_args.args[0]
        assert isinstance(email_call, RenderedNotification)
        assert email_call.channel == NotificationChannel.EMAIL
        assert email_call.destination == "qa@example.com"
        assert "[URGP]" in email_call.subject

        webhook_call = webhook_transport.send.await_args.args[0]
        assert isinstance(webhook_call, RenderedNotification)
        assert webhook_call.channel == NotificationChannel.WEBHOOK
        assert webhook_call.destination == "https://hooks.example.test/urgp"
        assert webhook_call.payload["schema_version"] == "v1"

    @pytest.mark.asyncio
    async def test_process_request_persists_delivery_outcomes(self) -> None:
        """After transport dispatch, notification records should reflect the delivery outcome."""
        manifest = _build_manifest()
        subscriptions = [_email_subscription()]
        request = _notification_request()

        fake_session = _FakeSessionContext(manifest, subscriptions)
        fake_factory = _FakeSessionFactory(fake_session)

        email_transport = MagicMock()
        email_transport.send = AsyncMock(return_value=None)

        settings = SimpleNamespace(
            portal_base_url="http://localhost:8000/portal",
            notification_max_retries=0,
            notification_retry_backoff_seconds=0.0,
        )

        orchestrator = NotificationOrchestrator(
            session_factory_provider=lambda: fake_factory,
            settings=settings,  # type: ignore[arg-type]
            renderer=NotificationRenderer(settings),  # type: ignore[arg-type]
            retry_policy=RetryPolicy(max_retries=0, base_backoff_seconds=0.0),
            transports={NotificationChannel.EMAIL: email_transport},
        )
        orchestrator._load_manifest = AsyncMock(return_value=manifest)  # type: ignore[method-assign]

        await orchestrator.process_request(request)

        # Verify that a notification record was created
        assert len(fake_session._notifications) == 1
        record = next(iter(fake_session._notifications.values()))
        assert record.channel == NotificationChannel.EMAIL
        assert record.recipient_snapshot == "qa@example.com"
        assert record.event_type == NotificationEventType.BUILD_COMPLETED

    @pytest.mark.asyncio
    async def test_process_request_records_transport_failure(self) -> None:
        """When transport fails all retries, the notification outcome should be 'failed'."""
        manifest = _build_manifest()
        subscriptions = [_webhook_subscription()]
        request = _notification_request()

        fake_session = _FakeSessionContext(manifest, subscriptions)
        fake_factory = _FakeSessionFactory(fake_session)

        failing_transport = MagicMock()
        failing_transport.send = AsyncMock(side_effect=RuntimeError("webhook down"))

        settings = SimpleNamespace(
            portal_base_url="http://localhost:8000/portal",
            notification_max_retries=1,
            notification_retry_backoff_seconds=0.0,
        )

        orchestrator = NotificationOrchestrator(
            session_factory_provider=lambda: fake_factory,
            settings=settings,  # type: ignore[arg-type]
            renderer=NotificationRenderer(settings),  # type: ignore[arg-type]
            retry_policy=RetryPolicy(max_retries=1, base_backoff_seconds=0.0),
            transports={NotificationChannel.WEBHOOK: failing_transport},
        )
        orchestrator._load_manifest = AsyncMock(return_value=manifest)  # type: ignore[method-assign]

        await orchestrator.process_request(request)

        # Transport should have been called 2 times (1 initial + 1 retry)
        assert failing_transport.send.await_count == 2

        # Notification record should exist with creation data
        assert len(fake_session._notifications) == 1
        record = next(iter(fake_session._notifications.values()))
        assert record.channel == NotificationChannel.WEBHOOK

    @pytest.mark.asyncio
    async def test_process_request_validates_build_id_mismatch(self) -> None:
        """Request referencing a different build_id than the manifest should raise."""
        manifest = _build_manifest()
        bad_request = NotificationRequest(
            manifest_id=_MANIFEST_ID,
            build_id="999999",  # mismatch!
            product_id="S32_IDE",
            event_type=NotificationEventType.BUILD_COMPLETED,
            triggered_at=datetime.now(tz=UTC),
            trigger_source="test",
        )

        fake_session = _FakeSessionContext(manifest, [])
        fake_factory = _FakeSessionFactory(fake_session)

        settings = SimpleNamespace(
            portal_base_url="http://localhost:8000/portal",
            notification_max_retries=0,
            notification_retry_backoff_seconds=0.0,
        )

        orchestrator = NotificationOrchestrator(
            session_factory_provider=lambda: fake_factory,
            settings=settings,  # type: ignore[arg-type]
            retry_policy=RetryPolicy(max_retries=0, base_backoff_seconds=0.0),
        )
        orchestrator._load_manifest = AsyncMock(return_value=manifest)  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="does not match manifest"):
            await orchestrator.process_request(bad_request)

    @pytest.mark.asyncio
    async def test_process_request_no_subscriptions_is_noop(self) -> None:
        """When no active subscriptions match, process_request should complete without errors."""
        manifest = _build_manifest()
        request = _notification_request()

        fake_session = _FakeSessionContext(manifest, [])  # No subscriptions
        fake_factory = _FakeSessionFactory(fake_session)

        settings = SimpleNamespace(
            portal_base_url="http://localhost:8000/portal",
            notification_max_retries=0,
            notification_retry_backoff_seconds=0.0,
        )

        orchestrator = NotificationOrchestrator(
            session_factory_provider=lambda: fake_factory,
            settings=settings,  # type: ignore[arg-type]
            retry_policy=RetryPolicy(max_retries=0, base_backoff_seconds=0.0),
        )
        orchestrator._load_manifest = AsyncMock(return_value=manifest)  # type: ignore[method-assign]

        # Should complete without errors or transport calls
        await orchestrator.process_request(request)
        assert len(fake_session._notifications) == 0
