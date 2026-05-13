"""Control-plane identity refactor for product/build/traceability uniqueness.

Revision ID: 002_control_plane_identity
Revises: 001_initial
Create Date: 2026-04-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "002_control_plane_identity"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Align relational identities with the ingestion contract."""
    op.add_column("products", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE products
        SET external_id = trim(both '-' from regexp_replace(lower(name), '[^a-z0-9]+', '-', 'g'))
        WHERE external_id IS NULL
        """
    )
    op.alter_column("products", "external_id", nullable=False)
    op.create_unique_constraint("uq_products_external_id", "products", ["external_id"])

    op.create_unique_constraint("uq_releases_product_version", "releases", ["product_id", "version"])

    op.drop_index("ix_build_manifests_build_id", table_name="build_manifests")
    op.create_index("ix_build_manifests_build_id", "build_manifests", ["build_id"], unique=False)
    op.create_unique_constraint(
        "uq_build_manifests_product_build",
        "build_manifests",
        ["product_id", "build_id"],
    )

    op.drop_index("ix_commits_hash", table_name="commits")
    op.create_index("ix_commits_hash", "commits", ["hash"], unique=False)
    op.create_unique_constraint("uq_commits_repository_hash", "commits", ["repository", "hash"])

    op.create_unique_constraint(
        "uq_pull_requests_repository_external_id",
        "pull_requests",
        ["repository", "external_id"],
    )
    op.create_unique_constraint(
        "uq_issues_tracker_external_id",
        "issues",
        ["tracker_type", "external_id"],
    )


def downgrade() -> None:
    """Restore the original identity model."""
    op.drop_constraint("uq_issues_tracker_external_id", "issues", type_="unique")
    op.drop_constraint("uq_pull_requests_repository_external_id", "pull_requests", type_="unique")

    op.drop_constraint("uq_commits_repository_hash", "commits", type_="unique")
    op.drop_index("ix_commits_hash", table_name="commits")
    op.create_index("ix_commits_hash", "commits", ["hash"], unique=True)

    op.drop_constraint("uq_build_manifests_product_build", "build_manifests", type_="unique")
    op.drop_index("ix_build_manifests_build_id", table_name="build_manifests")
    op.create_index("ix_build_manifests_build_id", "build_manifests", ["build_id"], unique=True)

    op.drop_constraint("uq_releases_product_version", "releases", type_="unique")

    op.drop_constraint("uq_products_external_id", "products", type_="unique")
    op.drop_column("products", "external_id")
