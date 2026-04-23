"""Initial URGP schema: 12 tables, 5 enums, and baseline indexes.

Revision ID: 001_initial
Revises: None
Create Date: 2026-04-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial URGP database schema."""
    build_status_enum = sa.Enum(
        "ingesting",
        "hydrating",
        "completed",
        "testing",
        "released",
        "deprecated",
        name="build_status",
    )
    artifact_type_enum = sa.Enum(
        "eclipse_p2",
        "oci_image",
        "binary",
        "npm_tarball",
        "maven_jar",
        "python_wheel",
        "generic",
        name="artifact_type",
    )
    notification_channel_enum = sa.Enum(
        "email",
        "webhook",
        name="notification_channel",
    )
    build_type_enum = sa.Enum(
        "nightly",
        "weekly",
        "rc",
        "hotfix",
        name="build_type",
    )
    user_role_enum = sa.Enum(
        "platform_admin",
        "product_admin",
        "developer",
        "tester",
        "viewer",
        name="user_role",
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("git_config", JSONB, nullable=True),
        sa.Column("issue_config", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "releases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("release_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "build_manifests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("build_id", sa.String(255), nullable=False, unique=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("release_id", UUID(as_uuid=True), sa.ForeignKey("releases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("build_type", build_type_enum, nullable=False),
        sa.Column("status", build_status_enum, nullable=False, server_default="ingesting"),
        sa.Column("traceability_incomplete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sbom_reference", sa.String(500), nullable=True),
        sa.Column("signature", sa.String(128), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cli_version", sa.String(50), nullable=True),
        sa.Column("ci_metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_build_manifests_build_id", "build_manifests", ["build_id"], unique=True)
    op.create_index("ix_build_manifests_product_created", "build_manifests", ["product_id", "created_at"])
    op.create_index("ix_build_manifests_status", "build_manifests", ["status"])

    op.create_table(
        "artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "manifest_id",
            UUID(as_uuid=True),
            sa.ForeignKey("build_manifests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("type", artifact_type_enum, nullable=False),
        sa.Column("storage_uri", sa.String(1000), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256_checksum"])

    op.create_table(
        "commits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hash", sa.String(40), nullable=False, unique=True),
        sa.Column("repository", sa.String(500), nullable=False),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_commits_hash", "commits", ["hash"], unique=True)

    op.create_table(
        "pull_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("repository", sa.String(500), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("source_branch", sa.String(255), nullable=True),
        sa.Column("target_branch", sa.String(255), nullable=True),
        sa.Column("merge_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "issues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("tracker_type", sa.String(50), nullable=False, server_default="jira"),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("assignee", sa.String(255), nullable=True),
        sa.Column("labels", JSONB, nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "build_commits",
        sa.Column(
            "build_id",
            UUID(as_uuid=True),
            sa.ForeignKey("build_manifests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "commit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("commits.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "commit_prs",
        sa.Column(
            "commit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("commits.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "pr_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "commit_issues",
        sa.Column(
            "commit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("commits.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "issue_id",
            UUID(as_uuid=True),
            sa.ForeignKey("issues.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "notification_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "release_id",
            UUID(as_uuid=True),
            sa.ForeignKey("releases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("webhook_url", sa.String(1000), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "manifest_id",
            UUID(as_uuid=True),
            sa.ForeignKey("build_manifests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("recipient", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Drop all URGP tables and enums."""
    op.drop_table("notifications")
    op.drop_table("notification_subscriptions")
    op.drop_table("commit_issues")
    op.drop_table("commit_prs")
    op.drop_table("build_commits")
    op.drop_table("issues")
    op.drop_table("pull_requests")
    op.drop_table("commits")
    op.drop_table("artifacts")
    op.drop_table("build_manifests")
    op.drop_table("releases")
    op.drop_table("products")

    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="build_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_channel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="artifact_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="build_status").drop(op.get_bind(), checkfirst=True)
