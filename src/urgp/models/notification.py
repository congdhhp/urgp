"""Notification models — Subscriptions and Notification records.

Reference: docs/05-technical-design.md § Data Model (notification_subscriptions, notifications)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from urgp.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from urgp.models.enums import NotificationChannel, NotificationEventType

if TYPE_CHECKING:
    from urgp.models.manifest import BuildManifest
    from urgp.models.product import Product, Release


def _enum_values(enum_type: type[NotificationChannel] | type[NotificationEventType]) -> list[str]:
    return [member.value for member in enum_type]


notification_channel_enum = Enum(
    NotificationChannel,
    name="notification_channel",
    values_callable=_enum_values,
)
notification_event_type_enum = Enum(
    NotificationEventType,
    name="notification_event_type",
    values_callable=_enum_values,
)


class NotificationSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Notification subscription entity.

    Users subscribe to notifications for specific product + release + channel combinations.
    """

    __tablename__ = "notification_subscriptions"
    __table_args__ = (
        Index(
            "uq_notification_subscriptions_identity",
            "user_id",
            "product_id",
            text("coalesce(release_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "channel",
            text("coalesce(webhook_url, '')"),
            unique=True,
        ),
    )

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
    channel: Mapped[NotificationChannel] = mapped_column(notification_channel_enum, nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # Required when channel=webhook
    active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    product: Mapped[Product] = relationship("Product", back_populates="subscriptions")
    release: Mapped[Release | None] = relationship("Release", back_populates="subscriptions")
    notifications: Mapped[list[Notification]] = relationship("Notification", back_populates="subscription")

    def __repr__(self) -> str:
        return f"<NotificationSubscription(user='{self.user_id}', channel={self.channel})>"


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Notification record entity.

    Records each notification sent, for tracking delivery status and history.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "manifest_id",
            "subscription_id",
            "event_type",
            name="uq_notifications_manifest_subscription_event",
        ),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_status", "status"),
    )

    manifest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("build_manifests.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[NotificationEventType] = mapped_column(notification_event_type_enum, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(notification_channel_enum, nullable=False)
    recipient_snapshot: Mapped[str] = mapped_column(String(1000), nullable=False)  # Email address or webhook URL
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, sent, failed
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    manifest: Mapped[BuildManifest] = relationship("BuildManifest", back_populates="notifications")
    subscription: Mapped[NotificationSubscription] = relationship("NotificationSubscription", back_populates="notifications")

    def __repr__(self) -> str:
        return (
            f"<Notification(manifest={self.manifest_id}, event_type={self.event_type}, "
            f"channel={self.channel}, status='{self.status}')>"
        )
