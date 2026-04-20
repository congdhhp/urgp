"""Database enums used across URGP models.

Reference: docs/05-technical-design.md § Core Enums
"""

from __future__ import annotations

import enum


class BuildStatus(str, enum.Enum):
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


class ArtifactType(str, enum.Enum):
    """Supported artifact types."""

    ECLIPSE_P2 = "eclipse_p2"
    OCI_IMAGE = "oci_image"
    BINARY = "binary"
    NPM_TARBALL = "npm_tarball"
    MAVEN_JAR = "maven_jar"
    PYTHON_WHEEL = "python_wheel"
    GENERIC = "generic"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"


class BuildType(str, enum.Enum):
    """Build type classification."""

    NIGHTLY = "nightly"
    WEEKLY = "weekly"
    RC = "rc"
    HOTFIX = "hotfix"


class UserRole(str, enum.Enum):
    """User roles for RBAC (Phase 2, defined here for schema completeness)."""

    PLATFORM_ADMIN = "platform_admin"
    PRODUCT_ADMIN = "product_admin"
    DEVELOPER = "developer"
    TESTER = "tester"
    VIEWER = "viewer"
