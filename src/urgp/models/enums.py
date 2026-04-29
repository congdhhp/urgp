"""Database enums used across URGP models.

Reference: docs/05-technical-design.md § Core Enums
"""

from __future__ import annotations

import enum


class BuildStatus(enum.StrEnum):
    """Build lifecycle status.

    State machine transitions:
        ingesting → hydrating → completed → testing → released → deprecated
        completed → deprecated (skip testing)
    """

    INGESTING = "ingesting"
    HYDRATING = "hydrating"
    COMPLETED = "completed"
    TESTING = "testing"
    RELEASED = "released"
    DEPRECATED = "deprecated"


class ArtifactType(enum.StrEnum):
    """Supported artifact types."""

    ECLIPSE_P2 = "eclipse_p2"
    OCI_IMAGE = "oci_image"
    BINARY = "binary"
    NPM_TARBALL = "npm_tarball"
    MAVEN_JAR = "maven_jar"
    PYTHON_WHEEL = "python_wheel"
    GENERIC = "generic"


class NotificationChannel(enum.StrEnum):
    """Notification delivery channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationEventType(enum.StrEnum):
    """Lifecycle events that trigger notification fan-out."""

    BUILD_COMPLETED = "build_completed"
    BUILD_RELEASED = "build_released"


class NotificationDeliveryStatus(enum.StrEnum):
    """Persisted delivery states for a notification attempt."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class BuildType(enum.StrEnum):
    """Build type classification."""

    NIGHTLY = "nightly"
    WEEKLY = "weekly"
    RC = "rc"
    HOTFIX = "hotfix"


class UserRole(enum.StrEnum):
    """User roles for RBAC (Phase 2, defined here for schema completeness)."""

    PLATFORM_ADMIN = "platform_admin"
    PRODUCT_ADMIN = "product_admin"
    DEVELOPER = "developer"
    TESTER = "tester"
    VIEWER = "viewer"
