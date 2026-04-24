"""Tests for Jira issue tracker adapter (P1-4.T5).

Tests JiraTracker with mocked HTTP responses covering single issue retrieval,
batch queries, caching, missing issues, and factory creation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from urgp.integrations.issues.base import IssueTrackerAPIError
from urgp.integrations.issues.jira import JiraTracker
from urgp.services.cache import CacheService

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _jira_issue_response(key: str = "PROJ-123") -> dict:
    return {
        "key": key,
        "self": f"https://jira.example.com/rest/api/3/issue/{key}",
        "fields": {
            "summary": "Resolve GPIO pin mapping for S32K3",
            "status": {"name": "In Review"},
            "priority": {"name": "Critical"},
            "assignee": {"displayName": "John Doe"},
            "labels": ["backend", "s32k3"],
            "issuetype": {"name": "Bug"},
        },
    }


def _jira_search_response(keys: list[str]) -> dict:
    return {
        "total": len(keys),
        "issues": [_jira_issue_response(key) for key in keys],
    }


def _mock_cache() -> CacheService:
    return CacheService(None)


def _mock_cache_with_redis() -> CacheService:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=None)
    return CacheService(redis, default_ttl=300)


# ─────────────────────────────────────────────
# Single Issue Retrieval Tests
# ─────────────────────────────────────────────


class TestJiraTrackerGetIssue:
    """Test single issue retrieval."""

    async def test_get_issue_successfully(self) -> None:
        """P1-4.T5: Retrieve a single Jira issue by key."""
        issue_data = _jira_issue_response("PROJ-123")
        tracker = JiraTracker("https://jira.example.com", token="test-token")
        tracker._api_get = AsyncMock(return_value=issue_data)  # type: ignore[method-assign]

        result = await tracker.get_issue("PROJ-123")
        assert result is not None
        assert result.external_id == "PROJ-123"
        assert result.tracker_type == "jira"
        assert result.title == "Resolve GPIO pin mapping for S32K3"
        assert result.status == "In Review"
        assert result.priority == "Critical"
        assert result.assignee == "John Doe"
        assert result.labels == ["backend", "s32k3"]
        assert result.url == "https://jira.example.com/browse/PROJ-123"

    async def test_get_issue_not_found_returns_none(self) -> None:
        """P1-4.T5: Missing issue returns None (no exception)."""
        tracker = JiraTracker("https://jira.example.com", token="test-token")
        tracker._api_get = AsyncMock(  # type: ignore[method-assign]
            side_effect=IssueTrackerAPIError("Not found", status_code=404)
        )

        result = await tracker.get_issue("PROJ-999")
        assert result is None

    async def test_get_issue_with_cache_hit(self) -> None:
        """P1-4.T5: Cache hit returns cached issue without API call."""
        issue_data = _jira_issue_response("PROJ-123")
        cache = _mock_cache_with_redis()
        cache.get_json = AsyncMock(return_value=issue_data)  # type: ignore[method-assign]

        tracker = JiraTracker("https://jira.example.com", token="test-token", cache=cache)
        tracker._api_get = AsyncMock()  # type: ignore[method-assign]

        result = await tracker.get_issue("PROJ-123")
        assert result is not None
        assert result.external_id == "PROJ-123"
        tracker._api_get.assert_not_called()


# ─────────────────────────────────────────────
# Batch Query Tests
# ─────────────────────────────────────────────


class TestJiraTrackerBatchGet:
    """Test batch issue retrieval via JQL."""

    async def test_batch_get_multiple_issues(self) -> None:
        """P1-4.T5: Batch retrieve multiple issues via JQL search."""
        keys = ["PROJ-101", "PROJ-102", "PROJ-103"]
        search_response = _jira_search_response(keys)

        tracker = JiraTracker("https://jira.example.com", token="test-token")
        tracker._jql_search = AsyncMock(return_value=search_response["issues"])  # type: ignore[method-assign]

        results = await tracker.batch_get(set(keys))
        assert len(results) == 3
        assert "PROJ-101" in results
        assert "PROJ-102" in results
        assert "PROJ-103" in results
        assert results["PROJ-101"].title == "Resolve GPIO pin mapping for S32K3"

    async def test_batch_get_empty_set(self) -> None:
        """P1-4.T5: Empty issue set returns empty dict."""
        tracker = JiraTracker("https://jira.example.com", token="test-token")
        results = await tracker.batch_get(set())
        assert results == {}

    async def test_batch_get_partial_failure(self) -> None:
        """P1-4.T5: Partial JQL failure returns what we got."""
        tracker = JiraTracker("https://jira.example.com", token="test-token")
        tracker._jql_search = AsyncMock(  # type: ignore[method-assign]
            side_effect=IssueTrackerAPIError("Search failed")
        )

        results = await tracker.batch_get({"PROJ-101", "PROJ-102"})
        assert results == {}  # Graceful empty, not exception


# ─────────────────────────────────────────────
# Connection Test
# ─────────────────────────────────────────────


class TestJiraTrackerTestConnection:
    """Test connection validation."""

    async def test_valid_connection(self) -> None:
        """P1-4.T5: Successful connection test."""
        tracker = JiraTracker("https://jira.example.com", token="test-token")
        tracker._api_get = AsyncMock(return_value={"serverTitle": "Jira"})  # type: ignore[method-assign]

        result = await tracker.test_connection()
        assert result is True

    async def test_invalid_connection(self) -> None:
        """P1-4.T5: Failed connection test."""
        tracker = JiraTracker("https://jira.example.com", token="bad-token")
        tracker._api_get = AsyncMock(  # type: ignore[method-assign]
            side_effect=IssueTrackerAPIError("Unauthorized", status_code=401)
        )

        result = await tracker.test_connection()
        assert result is False


# ─────────────────────────────────────────────
# Factory Tests
# ─────────────────────────────────────────────


class TestIssueTrackerFactory:
    """Test the create_issue_tracker factory function."""

    def test_jira_tracker_from_config(self) -> None:
        from urgp.integrations.issues import create_issue_tracker

        tracker = create_issue_tracker(
            {
                "tracker": "jira",
                "token": "test-token",
                "api_base_url": "https://jira.example.com",
            }
        )
        assert tracker is not None
        assert isinstance(tracker, JiraTracker)

    def test_jira_with_email_auth(self) -> None:
        from urgp.integrations.issues import create_issue_tracker

        tracker = create_issue_tracker(
            {
                "tracker": "jira",
                "token": "test-token",
                "api_base_url": "https://jira.example.com",
                "email": "admin@example.com",
            }
        )
        assert tracker is not None
        assert isinstance(tracker, JiraTracker)
        assert tracker._email == "admin@example.com"

    def test_none_config_returns_none(self) -> None:
        from urgp.integrations.issues import create_issue_tracker

        tracker = create_issue_tracker(None)
        assert tracker is None

    def test_empty_token_returns_none(self) -> None:
        from urgp.integrations.issues import create_issue_tracker

        tracker = create_issue_tracker({"tracker": "jira", "token": "", "api_base_url": "https://jira.example.com"})
        assert tracker is None

    def test_missing_api_base_url_returns_none(self) -> None:
        from urgp.integrations.issues import create_issue_tracker

        tracker = create_issue_tracker({"tracker": "jira", "token": "test-token"})
        assert tracker is None

    def test_unknown_tracker_returns_none(self) -> None:
        from urgp.integrations.issues import create_issue_tracker

        tracker = create_issue_tracker(
            {
                "tracker": "gitlab",
                "token": "test-token",
                "api_base_url": "https://gitlab.example.com",
            }
        )
        assert tracker is None
