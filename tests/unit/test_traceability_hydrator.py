"""Tests for the Traceability Hydrator (P1-4.T6, P1-4.T7).

Tests the refactored hydrator with both payload-only and external API
enrichment scenarios, including multi-repo builds and partial failures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from urgp.integrations.git.base import GitCommitDetail, GitProvider, GitProviderAPIError, GitPullRequestDetail
from urgp.integrations.issues.base import IssueDetail, IssueTracker
from urgp.models.enums import ArtifactType, BuildType
from urgp.schemas.ingest import ArtifactSchema, CommitHashSchema, IngestPayload
from urgp.services.cache import CacheService

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.default_issue_regex = r"\b[A-Z][A-Z0-9]+-\d+\b"
    settings.default_issue_tracker = "jira"
    return settings


def _make_manifest(product_name: str = "TestProduct") -> MagicMock:
    manifest = MagicMock()
    manifest.id = "00000000-0000-0000-0000-000000000001"
    manifest.build_id = "260330"
    manifest.product = MagicMock()
    manifest.product.name = product_name
    manifest.product.git_config = {"provider": "github", "token": "test"}
    manifest.product.issue_config = {"tracker": "jira", "issue_regex": r"\b[A-Z][A-Z0-9]+-\d+\b"}
    manifest.product.external_id = "test-product"
    manifest.commits = []
    return manifest


def _make_payload(
    *,
    commits: list[CommitHashSchema] | None = None,
) -> IngestPayload:
    if commits is None:
        commits = [
            CommitHashSchema(
                repository="org/repo-a",
                hash="a" * 40,
                branch="main",
                author="Alice",
                message="fix: PROJ-123 resolve GPIO issue",
                committed_at=datetime(2026, 3, 30, 10, 0, 0, tzinfo=UTC),
            ),
        ]

    return IngestPayload(
        product_id="test-product",
        release="3.6.8-RFP",
        build_type=BuildType.NIGHTLY,
        build_id="260330",
        cli_version="1.0.0",
        commit_hashes=commits,
        artifacts=[
            ArtifactSchema(
                name="s32-ide.zip",
                type=ArtifactType.GENERIC,
                storage_uri="https://artifacts.internal/s32-ide.zip",
                sha256="a" * 64,
            ),
        ],
        timestamp=datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC),
    )


def _make_mock_session() -> MagicMock:
    """Create a mock SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_git_provider() -> MagicMock:
    provider = MagicMock(spec=GitProvider)
    provider.get_commit = AsyncMock(
        return_value=GitCommitDetail(
            repository="org/repo-a",
            hash="a" * 40,
            author="Alice (API)",
            message="fix: PROJ-123 resolve GPIO issue (enriched)",
            committed_at=datetime(2026, 3, 30, 10, 0, 0, tzinfo=UTC),
            url="https://github.com/org/repo-a/commit/" + "a" * 40,
        )
    )
    provider.find_pull_requests = AsyncMock(
        return_value=[
            GitPullRequestDetail(
                external_id="456",
                repository="org/repo-a",
                title="GPIO Fix PR",
                author="alice",
                source_branch="feature/gpio",
                target_branch="main",
                merge_timestamp=datetime(2026, 3, 29, 15, 0, 0, tzinfo=UTC),
                url="https://github.com/org/repo-a/pull/456",
            )
        ]
    )
    return provider


def _make_issue_tracker() -> MagicMock:
    tracker = MagicMock(spec=IssueTracker)
    tracker.batch_get = AsyncMock(
        return_value={
            "PROJ-123": IssueDetail(
                external_id="PROJ-123",
                tracker_type="jira",
                title="GPIO pin mapping issue",
                status="In Progress",
                priority="Critical",
                assignee="Alice",
                labels=["s32k3"],
                url="https://jira.example.com/browse/PROJ-123",
            ),
        }
    )
    return tracker


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────


class TestTraceabilityHydratorPayloadOnly:
    """Test hydrator with payload data only (no external APIs)."""

    async def test_hydrate_with_payload_data(self) -> None:
        """P1-4.T6: Hydrate traceability graph from payload-supplied commit data."""
        from urgp.services.traceability import TraceabilityHydrator

        session = _make_mock_session()
        settings = _make_settings()
        manifest = _make_manifest()
        payload = _make_payload()

        # Mock the commit lookup to return a mock Commit object
        mock_commit = MagicMock()
        mock_commit.id = "commit-uuid-1"
        mock_commit.branch = None
        mock_commit.author = None
        mock_commit.message = None
        mock_commit.committed_at = None
        session.scalar = AsyncMock(return_value=mock_commit)

        hydrator = TraceabilityHydrator(session, settings)
        result = await hydrator.hydrate(manifest, payload)

        assert result.commit_count == 1
        assert result.issue_count >= 1  # PROJ-123 extracted from commit message
        assert result.traceability_incomplete is False

    async def test_hydrate_missing_commit_sets_incomplete(self) -> None:
        """P1-4.T7: Missing commits set traceability_incomplete flag."""
        from urgp.services.traceability import TraceabilityHydrator

        session = _make_mock_session()
        settings = _make_settings()
        manifest = _make_manifest()
        payload = _make_payload()

        # Commit not found in DB
        session.scalar = AsyncMock(return_value=None)

        hydrator = TraceabilityHydrator(session, settings)
        result = await hydrator.hydrate(manifest, payload)

        assert result.traceability_incomplete is True


class TestTraceabilityHydratorWithProviders:
    """Test hydrator with external API enrichment."""

    async def test_hydrate_enriches_from_git_api(self) -> None:
        """P1-4.T6: Git API enriches commit metadata."""
        from urgp.services.traceability import TraceabilityHydrator

        session = _make_mock_session()
        settings = _make_settings()
        manifest = _make_manifest()
        git_provider = _make_git_provider()
        payload = _make_payload()

        mock_commit = MagicMock()
        mock_commit.id = "commit-uuid-1"
        mock_commit.branch = None
        mock_commit.author = None
        mock_commit.message = None
        mock_commit.committed_at = None
        session.scalar = AsyncMock(return_value=mock_commit)

        hydrator = TraceabilityHydrator(
            session,
            settings,
            git_provider=git_provider,
        )
        result = await hydrator.hydrate(manifest, payload)

        # Git provider was called for enrichment
        git_provider.get_commit.assert_called_once()
        git_provider.find_pull_requests.assert_called_once()
        assert result.pull_request_count >= 1

    async def test_hydrate_enriches_from_issue_tracker(self) -> None:
        """P1-4.T6: Issue tracker enriches issue metadata."""
        from urgp.services.traceability import TraceabilityHydrator

        session = _make_mock_session()
        settings = _make_settings()
        manifest = _make_manifest()
        issue_tracker = _make_issue_tracker()
        payload = _make_payload()

        mock_commit = MagicMock()
        mock_commit.id = "commit-uuid-1"
        mock_commit.branch = None
        mock_commit.author = None
        mock_commit.message = None
        mock_commit.committed_at = None
        session.scalar = AsyncMock(return_value=mock_commit)

        hydrator = TraceabilityHydrator(
            session,
            settings,
            issue_tracker=issue_tracker,
        )
        result = await hydrator.hydrate(manifest, payload)

        # Issue tracker was called for enrichment
        issue_tracker.batch_get.assert_called_once()
        assert result.issue_count >= 1

    async def test_hydrate_git_api_failure_degrades_gracefully(self) -> None:
        """P1-4.T7: Git API failure falls back to payload data."""
        from urgp.services.traceability import TraceabilityHydrator

        session = _make_mock_session()
        settings = _make_settings()
        manifest = _make_manifest()
        git_provider = _make_git_provider()
        git_provider.get_commit = AsyncMock(
            side_effect=GitProviderAPIError("Server error", status_code=500, repository="org/repo-a")
        )
        git_provider.find_pull_requests = AsyncMock(
            side_effect=GitProviderAPIError("Server error", status_code=500, repository="org/repo-a")
        )

        payload = _make_payload()
        mock_commit = MagicMock()
        mock_commit.id = "commit-uuid-1"
        mock_commit.branch = None
        mock_commit.author = None
        mock_commit.message = None
        mock_commit.committed_at = None
        session.scalar = AsyncMock(return_value=mock_commit)

        hydrator = TraceabilityHydrator(
            session,
            settings,
            git_provider=git_provider,
        )
        result = await hydrator.hydrate(manifest, payload)

        # Should not raise, should proceed with payload data
        assert result.commit_count == 1


class TestTraceabilityHydratorMultiRepo:
    """Test hydrator with multi-repository builds."""

    async def test_multi_repo_commits(self) -> None:
        """P1-4.T6: Multi-repo build processes commits from different repos."""
        from urgp.services.traceability import TraceabilityHydrator

        session = _make_mock_session()
        settings = _make_settings()
        manifest = _make_manifest()

        commits = [
            CommitHashSchema(
                repository="org/repo-a",
                hash="a" * 40,
                branch="main",
                message="fix: PROJ-100 fix in repo A",
            ),
            CommitHashSchema(
                repository="org/repo-b",
                hash="b" * 40,
                branch="develop",
                message="feat: PROJ-200 feature in repo B",
            ),
            CommitHashSchema(
                repository="org/repo-c",
                hash="c" * 40,
                branch="main",
                message="chore: PROJ-300 cleanup in repo C",
            ),
        ]
        payload = _make_payload(commits=commits)

        def _make_mock_commit(idx: int) -> MagicMock:
            mc = MagicMock()
            mc.id = f"commit-uuid-{idx}"
            mc.branch = None
            mc.author = None
            mc.message = None
            mc.committed_at = None
            return mc

        # Scalar call pattern per commit:
        #   1. _load_commit → returns mock commit
        #   2. _ensure_issue → returns None (creates new issue)
        # Total for 3 commits: [commit0, None, commit1, None, commit2, None]
        session.scalar = AsyncMock(
            side_effect=[
                _make_mock_commit(0),
                None,  # commit 0 + issue PROJ-100
                _make_mock_commit(1),
                None,  # commit 1 + issue PROJ-200
                _make_mock_commit(2),
                None,  # commit 2 + issue PROJ-300
            ]
        )

        hydrator = TraceabilityHydrator(session, settings)
        result = await hydrator.hydrate(manifest, payload)

        assert result.commit_count == 3
        # 3 distinct issues: PROJ-100, PROJ-200, PROJ-300
        assert result.issue_count == 3
        assert result.traceability_incomplete is False


class TestCacheServiceUnit:
    """Test the CacheService."""

    async def test_no_redis_returns_none(self) -> None:
        cache = CacheService(None)
        result = await cache.get_json("any-key")
        assert result is None

    async def test_no_redis_set_is_noop(self) -> None:
        cache = CacheService(None)
        await cache.set_json("any-key", {"data": 1})  # Should not raise

    async def test_available_property(self) -> None:
        assert CacheService(None).available is False
        assert CacheService(MagicMock()).available is True

    async def test_redis_error_returns_none(self) -> None:
        redis = MagicMock()
        redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        cache = CacheService(redis)
        result = await cache.get_json("key")
        assert result is None  # Graceful degradation
