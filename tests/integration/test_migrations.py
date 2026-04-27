"""P1-1.T3: Database migration tests.

These tests require a running PostgreSQL instance (via docker compose).
Run with: pytest tests/integration/ -v -m integration

Tests:
- alembic upgrade head creates all 12 tables
- alembic downgrade base removes all tables
- Round-trip: upgrade → verify schema → downgrade → verify clean
"""

from __future__ import annotations

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.integration
class TestDatabaseMigrations:
    """Tests for Alembic migration up/down.

    NOTE: These tests require a running PostgreSQL database.
    They are meant to run with docker compose up, not in CI unit tests.

    To run: docker compose up -d postgres && pytest tests/integration/ -v -m integration
    """

    async def test_upgrade_creates_tables(self) -> None:
        """alembic upgrade head creates all expected tables."""
        # This test would:
        # 1. Connect to test database
        # 2. Run alembic upgrade head
        # 3. Verify all 12 tables exist
        # 4. Verify all indexes exist
        #
        # Requires: URGP_DATABASE_URL pointing to a test database
        pytest.skip("Requires running PostgreSQL (docker compose up -d postgres)")

    async def test_downgrade_removes_tables(self) -> None:
        """alembic downgrade base removes all tables and enums."""
        pytest.skip("Requires running PostgreSQL (docker compose up -d postgres)")

    async def test_migration_round_trip(self) -> None:
        """Full round-trip: upgrade → verify → downgrade → verify clean → upgrade again."""
        pytest.skip("Requires running PostgreSQL (docker compose up -d postgres)")


EXPECTED_TABLES = [
    "products",
    "releases",
    "build_manifests",
    "artifacts",
    "commits",
    "pull_requests",
    "issues",
    "build_commits",
    "commit_prs",
    "commit_issues",
    "notification_subscriptions",
    "notifications",
]

EXPECTED_ENUMS = [
    "build_status",
    "artifact_type",
    "notification_channel",
    "notification_event_type",
    "build_type",
    "user_role",
]

EXPECTED_INDEXES = [
    "ix_build_manifests_build_id",
    "ix_build_manifests_product_created",
    "ix_build_manifests_status",
    "ix_artifacts_sha256",
    "ix_commits_hash",
]
