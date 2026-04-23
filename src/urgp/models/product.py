"""Product and Release models.

Reference: docs/05-technical-design.md § Data Model (products, releases)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from urgp.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from urgp.models.manifest import BuildManifest
    from urgp.models.notification import NotificationSubscription


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Product entity.

    A product represents a software product (e.g., S32 Design Studio)
    with its Git and Issue tracker configuration.
    """

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("external_id", name="uq_products_external_id"),)

    external_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Git provider configuration (provider type, repos, credentials)
    git_config: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Issue tracker configuration (tracker type, project key, regex, credentials)
    issue_config: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    releases: Mapped[list[Release]] = relationship("Release", back_populates="product", cascade="all, delete-orphan")
    manifests: Mapped[list[BuildManifest]] = relationship(
        "BuildManifest", back_populates="product", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list[NotificationSubscription]] = relationship(
        "NotificationSubscription", back_populates="product"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, external_id='{self.external_id}', name='{self.name}')>"


class Release(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Release (Release Train) entity.

    A release represents a versioned release train within a product
    (e.g., '3.6.8-RFP' within S32 Design Studio).
    """

    __tablename__ = "releases"
    __table_args__ = (UniqueConstraint("product_id", "version", name="uq_releases_product_version"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    release_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "RFP", "GA", "Patch"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")  # active, maintenance, eol

    # Relationships
    product: Mapped[Product] = relationship("Product", back_populates="releases")
    manifests: Mapped[list[BuildManifest]] = relationship(
        "BuildManifest", back_populates="release", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list[NotificationSubscription]] = relationship(
        "NotificationSubscription", back_populates="release"
    )

    def __repr__(self) -> str:
        return f"<Release(id={self.id}, version='{self.version}')>"
