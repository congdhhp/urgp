"""URGP data models — SQLAlchemy ORM and Pydantic schemas.

Import all models here so Alembic can auto-detect them.
"""

from urgp.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from urgp.models.enums import ArtifactType, BuildStatus, BuildType, NotificationChannel, UserRole
from urgp.models.manifest import Artifact, BuildManifest
from urgp.models.notification import Notification, NotificationSubscription
from urgp.models.product import Product, Release
from urgp.models.traceability import (
    Commit,
    Issue,
    PullRequest,
    build_commits,
    commit_issues,
    commit_prs,
)

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # Enums
    "ArtifactType",
    "BuildStatus",
    "BuildType",
    "NotificationChannel",
    "UserRole",
    # Product
    "Product",
    "Release",
    # Manifest
    "BuildManifest",
    "Artifact",
    # Traceability
    "Commit",
    "PullRequest",
    "Issue",
    "build_commits",
    "commit_prs",
    "commit_issues",
    # Notification
    "NotificationSubscription",
    "Notification",
]
