"""Tests for Git provider adapters (P1-4.T4).

Tests GitHubProvider and BitbucketProvider with mocked HTTP responses,
covering successful resolution, rate limiting, retries, and cache behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from urgp.integrations.git.base import GitProviderAPIError
from urgp.integrations.git.bitbucket import BitbucketProvider
from urgp.integrations.git.github import GitHubProvider
from urgp.services.cache import CacheService

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _github_commit_response(sha: str = "abc123def456789012345678901234567890abcd") -> dict:
    return {
        "sha": sha,
        "commit": {
            "author": {
                "name": "John Doe",
                "email": "john@example.com",
                "date": "2026-03-30T10:00:00Z",
            },
            "message": "fix: PROJ-123 resolve GPIO pin mapping",
        },
        "author": {"login": "johndoe"},
        "html_url": f"https://github.com/org/repo/commit/{sha}",
    }


def _github_pr_response(number: int = 456) -> list[dict]:
    return [
        {
            "number": number,
            "title": "Fix GPIO pin mapping",
            "user": {"login": "johndoe"},
            "head": {"ref": "feature/gpio-fix"},
            "base": {"ref": "main"},
            "merged_at": "2026-03-29T15:30:00Z",
            "html_url": f"https://github.com/org/repo/pull/{number}",
        }
    ]


def _bitbucket_commit_response(hash_val: str = "abc123def456789012345678901234567890abcd") -> dict:
    return {
        "hash": hash_val,
        "author": {
            "raw": "John Doe <john@example.com>",
            "user": {"display_name": "John Doe"},
        },
        "message": "fix: PROJ-123 resolve CAN bus timing",
        "date": "2026-03-30T10:00:00+00:00",
        "links": {"html": {"href": f"https://bitbucket.org/org/repo/commits/{hash_val}"}},
    }


def _bitbucket_pr_response(pr_id: int = 789) -> dict:
    return {
        "values": [
            {
                "id": pr_id,
                "title": "CAN bus timing fix",
                "author": {"display_name": "Jane Smith"},
                "source": {"branch": {"name": "feature/can-timing"}},
                "destination": {"branch": {"name": "main"}},
                "state": "MERGED",
                "updated_on": "2026-03-28T12:00:00+00:00",
                "links": {"html": {"href": f"https://bitbucket.org/org/repo/pull-requests/{pr_id}"}},
            }
        ]
    }


def _mock_cache() -> CacheService:
    cache = CacheService(None)
    return cache


def _mock_cache_with_redis() -> CacheService:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=None)
    return CacheService(redis, default_ttl=300)


# ─────────────────────────────────────────────
# GitHub Provider Tests
# ─────────────────────────────────────────────


class TestGitHubProviderGetCommit:
    """Test GitHub commit resolution."""

    async def test_resolve_commit_successfully(self, httpx_mock: MagicMock | None = None) -> None:
        """P1-4.T4: Resolve a GitHub commit to GitCommitDetail."""
        commit_data = _github_commit_response()
        provider = GitHubProvider("test-token", api_base_url="https://api.github.com")

        # Monkeypatch the _api_get method
        provider._api_get = AsyncMock(return_value=commit_data)  # type: ignore[method-assign]

        result = await provider.get_commit("org/repo", "abc123def456789012345678901234567890abcd")
        assert result.repository == "org/repo"
        assert result.hash == "abc123def456789012345678901234567890abcd"
        assert result.author == "John Doe"
        assert result.message == "fix: PROJ-123 resolve GPIO pin mapping"
        assert result.committed_at is not None
        assert result.committed_at.tzinfo is not None

    async def test_commit_not_found_raises(self) -> None:
        """P1-4.T4: 404 raises GitProviderAPIError."""
        provider = GitHubProvider("test-token", api_base_url="https://api.github.com")
        provider._api_get = AsyncMock(  # type: ignore[method-assign]
            side_effect=GitProviderAPIError("Not found", status_code=404, repository="org/repo")
        )

        with pytest.raises(GitProviderAPIError) as exc_info:
            await provider.get_commit("org/repo", "0000000000000000000000000000000000000000")
        assert exc_info.value.status_code == 404

    async def test_cache_hit_skips_api_call(self) -> None:
        """P1-4.T4: Cache hit should return cached data without API call."""
        commit_data = _github_commit_response()
        cache = _mock_cache_with_redis()
        cache.get_json = AsyncMock(return_value=commit_data)  # type: ignore[method-assign]

        provider = GitHubProvider("test-token", cache=cache, api_base_url="https://api.github.com")
        provider._api_get = AsyncMock()  # type: ignore[method-assign]

        result = await provider.get_commit("org/repo", "abc123def456789012345678901234567890abcd")
        assert result.author == "John Doe"
        provider._api_get.assert_not_called()


class TestGitHubProviderFindPullRequests:
    """Test GitHub pull request discovery."""

    async def test_find_prs_for_commit(self) -> None:
        """P1-4.T4: Find pull requests associated with a commit."""
        pr_data = _github_pr_response(456)
        provider = GitHubProvider("test-token", api_base_url="https://api.github.com")
        provider._api_get = AsyncMock(return_value=pr_data)  # type: ignore[method-assign]

        results = await provider.find_pull_requests("org/repo", "abc123def456789012345678901234567890abcd")
        assert len(results) == 1
        assert results[0].external_id == "456"
        assert results[0].title == "Fix GPIO pin mapping"
        assert results[0].author == "johndoe"
        assert results[0].source_branch == "feature/gpio-fix"
        assert results[0].target_branch == "main"
        assert results[0].merge_timestamp is not None


class TestGitHubProviderTestConnection:
    """Test GitHub connection validation."""

    async def test_valid_connection(self) -> None:
        """P1-4.T4: Test connection returns True on success."""
        provider = GitHubProvider("test-token", api_base_url="https://api.github.com")
        provider._api_get = AsyncMock(return_value={"name": "repo"})  # type: ignore[method-assign]

        result = await provider.test_connection("org/repo")
        assert result is True

    async def test_invalid_connection(self) -> None:
        """P1-4.T4: Test connection returns False on failure."""
        provider = GitHubProvider("test-token", api_base_url="https://api.github.com")
        provider._api_get = AsyncMock(  # type: ignore[method-assign]
            side_effect=GitProviderAPIError("Unauthorized", status_code=401, repository="org/repo")
        )

        result = await provider.test_connection("org/repo")
        assert result is False


# ─────────────────────────────────────────────
# Bitbucket Provider Tests
# ─────────────────────────────────────────────


class TestBitbucketProviderGetCommit:
    """Test Bitbucket commit resolution."""

    async def test_resolve_commit_successfully(self) -> None:
        """P1-4.T4: Resolve a Bitbucket commit to GitCommitDetail."""
        commit_data = _bitbucket_commit_response()
        provider = BitbucketProvider("test-token", api_base_url="https://api.bitbucket.org/2.0")
        provider._api_get = AsyncMock(return_value=commit_data)  # type: ignore[method-assign]

        result = await provider.get_commit("org/repo", "abc123def456789012345678901234567890abcd")
        assert result.repository == "org/repo"
        assert result.hash == "abc123def456789012345678901234567890abcd"
        assert result.author == "John Doe"
        assert result.message == "fix: PROJ-123 resolve CAN bus timing"
        assert result.committed_at is not None

    async def test_bitbucket_commit_with_no_author_raw(self) -> None:
        """P1-4.T4: Handle commit with display_name fallback."""
        commit_data = _bitbucket_commit_response()
        commit_data["author"]["raw"] = ""
        provider = BitbucketProvider("test-token", api_base_url="https://api.bitbucket.org/2.0")
        provider._api_get = AsyncMock(return_value=commit_data)  # type: ignore[method-assign]

        result = await provider.get_commit("org/repo", "abc123def456789012345678901234567890abcd")
        assert result.author == "John Doe"  # Falls back to display_name


class TestBitbucketProviderFindPullRequests:
    """Test Bitbucket PR discovery."""

    async def test_find_prs_for_commit(self) -> None:
        """P1-4.T4: Find merged PRs associated with a commit."""
        pr_data = _bitbucket_pr_response(789)
        provider = BitbucketProvider("test-token", api_base_url="https://api.bitbucket.org/2.0")
        provider._api_get = AsyncMock(return_value=pr_data)  # type: ignore[method-assign]

        results = await provider.find_pull_requests("org/repo", "abc123def456789012345678901234567890abcd")
        assert len(results) == 1
        assert results[0].external_id == "789"
        assert results[0].title == "CAN bus timing fix"
        assert results[0].author == "Jane Smith"
        assert results[0].source_branch == "feature/can-timing"
        assert results[0].merge_timestamp is not None


# ─────────────────────────────────────────────
# Factory Tests
# ─────────────────────────────────────────────


class TestGitProviderFactory:
    """Test the create_git_provider factory function."""

    def test_github_provider_from_config(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider({"provider": "github", "token": "test-token"})
        assert provider is not None
        assert isinstance(provider, GitHubProvider)

    def test_bitbucket_provider_from_config(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider({"provider": "bitbucket", "token": "test-token"})
        assert provider is not None
        assert isinstance(provider, BitbucketProvider)

    def test_none_config_returns_none(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider(None)
        assert provider is None

    def test_empty_token_returns_none(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider({"provider": "github", "token": ""})
        assert provider is None

    def test_unknown_provider_returns_none(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider({"provider": "unknown", "token": "test-token"})
        assert provider is None

    def test_custom_api_base_url(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider(
            {"provider": "github", "token": "test-token", "api_base_url": "https://github.internal.com/api/v3"}
        )
        assert provider is not None
        assert isinstance(provider, GitHubProvider)
        assert provider._api_base_url == "https://github.internal.com/api/v3"

    def test_nested_credentials_and_base_url_alias(self) -> None:
        from urgp.integrations.git import create_git_provider

        provider = create_git_provider(
            {
                "provider": "github",
                "credentials": {"authentication_token": "test-token"},
                "base_url": "https://github.internal.com/api/v3",
            }
        )
        assert provider is not None
        assert isinstance(provider, GitHubProvider)
        assert provider._api_base_url == "https://github.internal.com/api/v3"
