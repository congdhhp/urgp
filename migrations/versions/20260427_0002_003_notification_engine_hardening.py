"""Notification engine hardening for evented delivery history.

Revision ID: 003_notif_hardening
Revises: 002_control_plane_identity
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision: str = "003_notif_hardening"
down_revision: str | None = "002_control_plane_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Harden notification persistence and queue semantics."""
    notification_event_type_enum = sa.Enum(
        "build_completed",
        "build_released",
        name="notification_event_type",
    )
    notification_event_type_enum.create(op.get_bind(), checkfirst=True)

    op.execute(
        f"""
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY
                        user_id,
                        product_id,
                        coalesce(release_id, '{_ZERO_UUID}'::uuid),
                        channel,
                        coalesce(webhook_url, '')
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS rn
            FROM notification_subscriptions
        )
        DELETE FROM notification_subscriptions
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    op.add_column("notifications", sa.Column("subscription_id", UUID(as_uuid=True), nullable=True))
    op.add_column("notifications", sa.Column("event_type", notification_event_type_enum, nullable=True))
    op.add_column("notifications", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))

    op.alter_column("notifications", "recipient", new_column_name="recipient_snapshot")
    op.alter_column("notifications", "retry_count", new_column_name="attempt_count")
    op.alter_column("notifications", "error_message", new_column_name="last_error")

    op.execute("UPDATE notifications SET event_type = 'build_completed'")
    op.execute("UPDATE notifications SET last_attempt_at = COALESCE(sent_at, updated_at)")

    op.execute(
        """
        INSERT INTO notification_subscriptions (
            id,
            user_id,
            product_id,
            release_id,
            channel,
            webhook_url,
            active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            CASE
                WHEN n.channel = 'email' THEN n.recipient_snapshot
                ELSE 'legacy:webhook:' || md5(n.recipient_snapshot)
            END AS user_id,
            bm.product_id,
            bm.release_id,
            n.channel,
            CASE
                WHEN n.channel = 'webhook' THEN n.recipient_snapshot
                ELSE NULL
            END AS webhook_url,
            false,
            COALESCE(n.created_at, now()),
            COALESCE(n.updated_at, now())
        FROM notifications n
        JOIN build_manifests bm ON bm.id = n.manifest_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM notification_subscriptions ns
            WHERE ns.product_id = bm.product_id
              AND ns.release_id IS NOT DISTINCT FROM bm.release_id
              AND ns.channel = n.channel
              AND ns.user_id = CASE
                    WHEN n.channel = 'email' THEN n.recipient_snapshot
                    ELSE 'legacy:webhook:' || md5(n.recipient_snapshot)
                END
              AND ns.webhook_url IS NOT DISTINCT FROM CASE
                    WHEN n.channel = 'webhook' THEN n.recipient_snapshot
                    ELSE NULL
                END
        )
        """
    )

    op.execute(
        """
        UPDATE notifications n
        SET subscription_id = ns.id
        FROM build_manifests bm
        JOIN notification_subscriptions ns
          ON ns.product_id = bm.product_id
         AND ns.release_id IS NOT DISTINCT FROM bm.release_id
         AND ns.channel = n.channel
         AND ns.user_id = CASE
                WHEN n.channel = 'email' THEN n.recipient_snapshot
                ELSE 'legacy:webhook:' || md5(n.recipient_snapshot)
            END
         AND ns.webhook_url IS NOT DISTINCT FROM CASE
                WHEN n.channel = 'webhook' THEN n.recipient_snapshot
                ELSE NULL
            END
        WHERE bm.id = n.manifest_id
          AND n.subscription_id IS NULL
        """
    )

    op.execute(
        """
        DELETE FROM notifications n
        USING (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY manifest_id, subscription_id, event_type
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS rn
            FROM notifications
            WHERE subscription_id IS NOT NULL
        ) ranked
        WHERE n.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.alter_column("notifications", "subscription_id", nullable=False)
    op.alter_column("notifications", "event_type", nullable=False)
    op.create_foreign_key(
        "fk_notifications_subscription_id",
        "notifications",
        "notification_subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_notifications_manifest_subscription_event",
        "notifications",
        ["manifest_id", "subscription_id", "event_type"],
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)
    op.create_index("ix_notifications_status", "notifications", ["status"], unique=False)

    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_notification_subscriptions_identity
        ON notification_subscriptions (
            user_id,
            product_id,
            coalesce(release_id, '{_ZERO_UUID}'::uuid),
            channel,
            coalesce(webhook_url, '')
        )
        """
    )


def downgrade() -> None:
    """Restore the original notification schema."""
    op.execute("DROP INDEX IF EXISTS uq_notification_subscriptions_identity")

    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_constraint("uq_notifications_manifest_subscription_event", "notifications", type_="unique")
    op.drop_constraint("fk_notifications_subscription_id", "notifications", type_="foreignkey")

    op.alter_column("notifications", "last_error", new_column_name="error_message")
    op.alter_column("notifications", "attempt_count", new_column_name="retry_count")
    op.alter_column("notifications", "recipient_snapshot", new_column_name="recipient")

    op.drop_column("notifications", "last_attempt_at")
    op.drop_column("notifications", "event_type")
    op.drop_column("notifications", "subscription_id")

    sa.Enum(name="notification_event_type").drop(op.get_bind(), checkfirst=True)
