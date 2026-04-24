"""GitHub REST API v3 Git provider adapter.

Resolves commit metadata and associated pull requests via the GitHub API.

Reference:
- GET /repos/{owner}/{repo}/commits/{sha}
- GET /repos/{owner}/{repo}/commits/{sha}/pulls
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from urgp.integrations.git.base import (
    GitCommitDetail,
    GitProvider,
    GitProviderAPIError,
    GitPullRequestDetail,
)
from urgp.services.cache import CacheService

logger = logging.getLogger(__name__)

_DEFAULT_GITHUB_API = "https://api.github.com"
_API_TIMEOUT = 10.0
_MAX_RETRIES = 2


class GitHubProvider(GitProvider):
    """GitHub REST API v3 adapter for commit and pull request resolution."""

    def __init__(
        self,
        token: str,
        *,
        cache: CacheService | None = None,
        api_base_url: str = _DEFAULT_GITHUB_API,
    ) -> None:
        self._token = token
        self._cache = cache
        self._api_base_url = api_base_url.rstrip("/")

    async def get_commit(self, repository: str, commit_hash: str) -> GitCommitDetail:
        """Resolve a GitHub commit to full metadata."""
        cache_key = f"github:commit:{repository}:{commit_hash}"

        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                logger.debug("Cache hit for commit %s@%s", repository, commit_hash[:8])
                return _parse_commit_detail(repository, cached)

        url = f"{self._api_base_url}/repos/{repository}/commits/{commit_hash}"
        data = await self._api_get(url, repository=repository, commit_hash=commit_hash)

        if self._cache is not None:
            await self._cache.set_json(cache_key, data)

        return _parse_commit_detail(repository, data)

    async def find_pull_requests(self, repository: str, commit_hash: str) -> list[GitPullRequestDetail]:
        """Find PRs containing a commit via the GitHub commit-pulls endpoint."""
        cache_key = f"github:prs:{repository}:{commit_hash}"

        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                logger.debug("Cache hit for PRs %s@%s", repository, commit_hash[:8])
                return _parse_pull_requests(repository, cached)

        url = f"{self._api_base_url}/repos/{repository}/commits/{commit_hash}/pulls"
        data = await self._api_get(url, repository=repository, commit_hash=commit_hash)

        if self._cache is not None:
            await self._cache.set_json(cache_key, data)

        return _parse_pull_requests(repository, data)

    async def test_connection(self, repository: str) -> bool:
        """Test GitHub API connectivity by fetching the repository."""
        try:
            url = f"{self._api_base_url}/repos/{repository}"
            await self._api_get(url, repository=repository, commit_hash="")
            return True
        except GitProviderAPIError:
            return False

    async def _api_get(self, url: str, *, repository: str, commit_hash: str) -> Any:
        """Execute a GET request with retry, rate-limit handling, and error mapping."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code == 403 and "rate limit" in response.text.lower():
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(
                        "GitHub rate limit exceeded for %s; Retry-After=%s (attempt %d/%d)",
                        repository,
                        retry_after,
                        attempt,
                        _MAX_RETRIES + 1,
                    )
                    import asyncio

                    await asyncio.sleep(min(float(retry_after), 30.0))
                    continue

                if response.status_code == 404:
                    msg = f"GitHub resource not found: {url}"
                    raise GitProviderAPIError(msg, status_code=404, repository=repository)

                response.raise_for_status()
                return response.json()

            except GitProviderAPIError:
                raise
            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "GitHub API error %d for %s@%s (attempt %d/%d)",
                    exc.response.status_code,
                    repository,
                    commit_hash[:8] if commit_hash else "",
                    attempt,
                    _MAX_RETRIES + 1,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "GitHub API network error for %s@%s (attempt %d/%d): %s",
                    repository,
                    commit_hash[:8] if commit_hash else "",
                    attempt,
                    _MAX_RETRIES + 1,
                    str(exc),
                )

        msg = f"GitHub API call failed after {_MAX_RETRIES + 1} attempts: {last_error}"
        raise GitProviderAPIError(msg, repository=repository)


def _parse_commit_detail(repository: str, data: dict[str, Any]) -> GitCommitDetail:
    """Parse GitHub commit API response to GitCommitDetail."""
    commit_data = data.get("commit", {})
    author_data = commit_data.get("author", {})
    committed_at = None
    if author_data.get("date"):
        with contextlib.suppress(ValueError, TypeError):
            committed_at = datetime.fromisoformat(author_data["date"].replace("Z", "+00:00")).astimezone(UTC)

    return GitCommitDetail(
        repository=repository,
        hash=data.get("sha", ""),
        author=author_data.get("name") or (data.get("author") or {}).get("login"),
        message=commit_data.get("message"),
        committed_at=committed_at,
        url=data.get("html_url"),
    )


def _parse_pull_requests(repository: str, data: list[dict[str, Any]] | dict[str, Any]) -> list[GitPullRequestDetail]:
    """Parse GitHub pull request API response to list of GitPullRequestDetail."""
    if isinstance(data, dict):
        data = [data]

    results: list[GitPullRequestDetail] = []
    for pr_data in data:
        merge_timestamp = None
        if pr_data.get("merged_at"):
            with contextlib.suppress(ValueError, TypeError):
                merge_timestamp = datetime.fromisoformat(pr_data["merged_at"].replace("Z", "+00:00")).astimezone(UTC)

        results.append(
            GitPullRequestDetail(
                external_id=str(pr_data.get("number", "")),
                repository=repository,
                title=pr_data.get("title"),
                author=(pr_data.get("user") or {}).get("login"),
                source_branch=(pr_data.get("head") or {}).get("ref"),
                target_branch=(pr_data.get("base") or {}).get("ref"),
                merge_timestamp=merge_timestamp,
                url=pr_data.get("html_url"),
            )
        )
    return results


__all__ = [
    "GitHubProvider",
]
