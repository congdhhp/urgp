"""Unit tests for notification rendering and delivery safety."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from urgp.models.enums import BuildStatus, BuildType, NotificationChannel, NotificationEventType
from urgp.schemas.notifications import NotificationRequest
from urgp.services.notification_processing import NotificationRenderer


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.portal_base_url = "http://localhost:8000/portal"
    return settings


def _manifest() -> MagicMock:
    manifest = MagicMock()
    manifest.build_id = "260330"
    manifest.product = MagicMock()
    manifest.product.name = "S32 Design Studio"
    manifest.product.external_id = "S32_IDE"
    manifest.release = MagicMock()
    manifest.release.version = "3.6.8-RFP"
    manifest.build_type = BuildType.NIGHTLY
    manifest.status = BuildStatus.COMPLETED
    manifest.created_at = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)
    manifest.traceability_incomplete = False
    manifest.commits = []
    return manifest


class TestNotificationRendering:
    def test_render_notification_does_not_expose_webhook_url(self) -> None:
        renderer = NotificationRenderer(_settings())
        subscription = MagicMock()
        subscription.channel = NotificationChannel.WEBHOOK
        subscription.webhook_url = "https://hooks.example.com/urgp"
        subscription.user_id = "qa@example.com"

        request = NotificationRequest(
            manifest_id=uuid.uuid4(),
            build_id="260330",
            product_id="S32_IDE",
            event_type=NotificationEventType.BUILD_COMPLETED,
            triggered_at=datetime.now(tz=UTC),
            trigger_source="test",
        )

        rendered = renderer.render(_manifest(), subscription, request)

        assert "_webhook_url" not in rendered.payload
        assert rendered.channel == NotificationChannel.WEBHOOK
