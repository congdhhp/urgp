"""Build Manifest and Artifact models.

Reference: docs/05-technical-design.md § Data Model (build_manifests, artifacts)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from urgp.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from urgp.models.enums import ArtifactType, BuildStatus, BuildType

if TYPE_CHECKING:
    from urgp.models.notification import Notification
    from urgp.models.product import Product, Release
    from urgp.models.traceability import Commit


def _enum_values(enum_type: type[ArtifactType] | type[BuildStatus] | type[BuildType]) -> list[str]:
    return [member.value for member in enum_type]


artifact_type_enum = Enum(ArtifactType, name="artifact_type", values_callable=_enum_values)
build_status_enum = Enum(BuildStatus, name="build_status", values_callable=_enum_values)
build_type_enum = Enum(BuildType, name="build_type", values_callable=_enum_values)


class BuildManifest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Build Manifest entity.

    Represents a single build with its lifecycle status, artifacts,
    and traceability data. Manifests become immutable when status is 'released'.
    """

    __tablename__ = "build_manifests"
    __table_args__ = (
        UniqueConstraint("product_id", "build_id", name="uq_build_manifests_product_build"),
        Index("ix_build_manifests_build_id", "build_id"),
        Index("ix_build_manifests_product_created", "product_id", "created_at"),
        Index("ix_build_manifests_status", "status"),
    )

    build_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("releases.id", ondelete="SET NULL"),
        nullable=True,
    )
    build_type: Mapped[BuildType] = mapped_column(build_type_enum, nullable=False)
    status: Mapped[BuildStatus] = mapped_column(build_status_enum, nullable=False, default=BuildStatus.INGESTING)

    # Traceability
    traceability_incomplete: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Immutability
    sbom_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature: Mapped[str | None] = mapped_column(String(128), nullable=True)  # HMAC-SHA256

    # Metadata
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cli_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ci_metadata: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    product: Mapped[Product] = relationship("Product", back_populates="manifests")
    release: Mapped[Release | None] = relationship("Release", back_populates="manifests")
    artifacts: Mapped[list[Artifact]] = relationship(
        "Artifact", back_populates="manifest", cascade="all, delete-orphan"
    )
    commits: Mapped[list[Commit]] = relationship("Commit", secondary="build_commits", back_populates="manifests")
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="manifest", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BuildManifest(id={self.id}, build_id='{self.build_id}', status={self.status})>"


class Artifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Artifact entity.

    Represents a build output file with its SHA-256 checksum and metadata.
    """

    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_sha256", "sha256_checksum"),)

    manifest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("build_manifests.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[ArtifactType] = mapped_column(artifact_type_enum, nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hex digest
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Technology-specific metadata (e.g., Eclipse P2 features, OCI layers)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    manifest: Mapped[BuildManifest] = relationship("BuildManifest", back_populates="artifacts")

    def __repr__(self) -> str:
        return f"<Artifact(id={self.id}, name='{self.name}', type={self.type})>"
