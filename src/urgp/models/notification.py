"""Notification models — Subscriptions and Notification records.

Reference: docs/05-technical-design.md § Data Model (notification_subscriptions, notifications)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from urgp.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from urgp.models.enums import NotificationChannel

if TYPE_CHECKING:
    from urgp.models.manifest import BuildManifest
    from urgp.models.product import Product, Release


class NotificationSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Notification subscription entity.

    Users subscribe to notifications for specific product + release + channel combinations.
    """

    __tablename__ = "notification_subscriptions"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False)  # User identifier
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
    channel: Mapped[NotificationChannel] = mapped_column(nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # Required when channel=webhook
    active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    product: Mapped[Product] = relationship("Product", back_populates="subscriptions")
    release: Mapped[Release | None] = relationship("Release", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<NotificationSubscription(user='{self.user_id}', channel={self.channel})>"


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Notification record entity.

    Records each notification sent, for tracking delivery status and history.
    """

    __tablename__ = "notifications"

    manifest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("build_manifests.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(nullable=False)
    recipient: Mapped[str] = mapped_column(String(500), nullable=False)  # Email address or webhook URL
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, sent, failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    manifest: Mapped[BuildManifest] = relationship("BuildManifest", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification(manifest={self.manifest_id}, channel={self.channel}, status='{self.status}')>"
