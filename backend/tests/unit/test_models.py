"""Unit tests for database models and enums."""

from __future__ import annotations

from urgp.models.enums import (
    ArtifactType,
    BuildStatus,
    BuildType,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    UserRole,
)


class TestBuildStatusEnum:
    """Tests for BuildStatus lifecycle enum."""

    def test_all_statuses_defined(self) -> None:
        """All 6 build statuses are defined."""
        statuses = list(BuildStatus)
        assert len(statuses) == 6

    def test_status_values(self) -> None:
        """Status values match the SQL enum definition."""
        assert BuildStatus.INGESTING.value == "ingesting"
        assert BuildStatus.HYDRATING.value == "hydrating"
        assert BuildStatus.COMPLETED.value == "completed"
        assert BuildStatus.TESTING.value == "testing"
        assert BuildStatus.RELEASED.value == "released"
        assert BuildStatus.DEPRECATED.value == "deprecated"

    def test_status_is_string(self) -> None:
        """BuildStatus inherits from str for JSON serialization."""
        assert isinstance(BuildStatus.RELEASED, str)
        assert BuildStatus.RELEASED == "released"


class TestArtifactTypeEnum:
    """Tests for ArtifactType enum."""

    def test_all_types_defined(self) -> None:
        """All 7 artifact types are defined."""
        types = list(ArtifactType)
        assert len(types) == 7

    def test_eclipse_p2_type(self) -> None:
        """Eclipse P2 type exists (primary S32 artifact type)."""
        assert ArtifactType.ECLIPSE_P2.value == "eclipse_p2"

    def test_generic_type(self) -> None:
        """Generic type exists as fallback."""
        assert ArtifactType.GENERIC.value == "generic"


class TestBuildTypeEnum:
    """Tests for BuildType enum."""

    def test_all_types_defined(self) -> None:
        """All 4 build types are defined."""
        types = list(BuildType)
        assert len(types) == 4
        values = {t.value for t in types}
        assert values == {"nightly", "weekly", "rc", "hotfix"}


class TestNotificationChannelEnum:
    """Tests for NotificationChannel enum."""

    def test_channels(self) -> None:
        """Email and webhook channels are defined."""
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert len(list(NotificationChannel)) == 2


class TestNotificationEventTypeEnum:
    """Tests for NotificationEventType enum."""

    def test_event_types(self) -> None:
        assert NotificationEventType.BUILD_COMPLETED.value == "build_completed"
        assert NotificationEventType.BUILD_RELEASED.value == "build_released"
        assert len(list(NotificationEventType)) == 2


class TestNotificationDeliveryStatusEnum:
    """Tests for NotificationDeliveryStatus enum."""

    def test_delivery_statuses(self) -> None:
        assert NotificationDeliveryStatus.PENDING.value == "pending"
        assert NotificationDeliveryStatus.SENT.value == "sent"
        assert NotificationDeliveryStatus.FAILED.value == "failed"
        assert len(list(NotificationDeliveryStatus)) == 3


class TestUserRoleEnum:
    """Tests for UserRole enum (forward-defined for Phase 2)."""

    def test_all_roles_defined(self) -> None:
        """All 5 user roles are defined."""
        roles = list(UserRole)
        assert len(roles) == 5
        values = {r.value for r in roles}
        assert "platform_admin" in values
        assert "viewer" in values
