"""Unit tests for notification rendering and delivery safety."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from urgp.models.enums import BuildStatus, BuildType, NotificationChannel
from urgp.services.notification_processing import NotificationProcessingService


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
        service = NotificationProcessingService(lambda: MagicMock(), _settings())
        subscription = MagicMock()
        subscription.channel = NotificationChannel.WEBHOOK
        subscription.webhook_url = "https://hooks.example.com/urgp"

        _, _, payload = service._render_notification(_manifest(), subscription)

        assert "_webhook_url" not in payload
        assert payload["subscription_channel"] == "webhook"
