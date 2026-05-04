"""Drop obsolete global commit hash uniqueness.

Revision ID: 004_drop_commit_hash_unique
Revises: 003_notif_hardening
Create Date: 2026-05-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_drop_commit_hash_unique"
down_revision: str | None = "003_notif_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow the same commit hash to be reused through repository-scoped identity."""
    op.execute("ALTER TABLE commits DROP CONSTRAINT IF EXISTS commits_hash_key")


def downgrade() -> None:
    """Restore the legacy global uniqueness constraint."""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'commits_hash_key'
            ) THEN
                ALTER TABLE commits ADD CONSTRAINT commits_hash_key UNIQUE (hash);
            END IF;
        END
        $$;
        """
    )
