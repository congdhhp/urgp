"""Bitbucket Cloud REST API v2 Git provider adapter.

Resolves commit metadata and associated pull requests via the Bitbucket API.

Reference:
- GET /repositories/{workspace}/{repo}/commit/{hash}
- GET /repositories/{workspace}/{repo}/pullrequests?q=source.commit.hash="{hash}"
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

_DEFAULT_BITBUCKET_API = "https://api.bitbucket.org/2.0"
_API_TIMEOUT = 10.0
_MAX_RETRIES = 2


class BitbucketProvider(GitProvider):
    """Bitbucket Cloud REST API v2 adapter for commit and pull request resolution."""

    def __init__(
        self,
        token: str,
        *,
        cache: CacheService | None = None,
        api_base_url: str = _DEFAULT_BITBUCKET_API,
    ) -> None:
        self._token = token
        self._cache = cache
        self._api_base_url = api_base_url.rstrip("/")

    async def get_commit(self, repository: str, commit_hash: str) -> GitCommitDetail:
        """Resolve a Bitbucket commit to full metadata."""
        cache_key = f"bitbucket:commit:{repository}:{commit_hash}"

        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                logger.debug("Cache hit for commit %s@%s", repository, commit_hash[:8])
                return _parse_commit_detail(repository, cached)

        url = f"{self._api_base_url}/repositories/{repository}/commit/{commit_hash}"
        data = await self._api_get(url, repository=repository, commit_hash=commit_hash)

        if self._cache is not None:
            await self._cache.set_json(cache_key, data)

        return _parse_commit_detail(repository, data)

    async def find_pull_requests(self, repository: str, commit_hash: str) -> list[GitPullRequestDetail]:
        """Find PRs associated with a commit via Bitbucket search."""
        cache_key = f"bitbucket:prs:{repository}:{commit_hash}"

        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                logger.debug("Cache hit for PRs %s@%s", repository, commit_hash[:8])
                return _parse_pull_requests(repository, cached)

        url = f"{self._api_base_url}/repositories/{repository}/pullrequests"
        params = {"q": f'source.commit.hash="{commit_hash}"', "state": "MERGED"}
        data = await self._api_get(url, repository=repository, commit_hash=commit_hash, params=params)

        if self._cache is not None:
            await self._cache.set_json(cache_key, data)

        return _parse_pull_requests(repository, data)

    async def test_connection(self, repository: str) -> bool:
        """Test Bitbucket API connectivity by fetching the repository."""
        try:
            url = f"{self._api_base_url}/repositories/{repository}"
            await self._api_get(url, repository=repository, commit_hash="")
            return True
        except GitProviderAPIError:
            return False

    async def _api_get(
        self,
        url: str,
        *,
        repository: str,
        commit_hash: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Execute a GET request with retry and error mapping."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                    response = await client.get(url, headers=headers, params=params)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(
                        "Bitbucket rate limit exceeded for %s; Retry-After=%s (attempt %d/%d)",
                        repository,
                        retry_after,
                        attempt,
                        _MAX_RETRIES + 1,
                    )
                    import asyncio

                    await asyncio.sleep(min(float(retry_after), 30.0))
                    continue

                if response.status_code == 404:
                    msg = f"Bitbucket resource not found: {url}"
                    raise GitProviderAPIError(msg, status_code=404, repository=repository)

                response.raise_for_status()
                return response.json()

            except GitProviderAPIError:
                raise
            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "Bitbucket API error %d for %s@%s (attempt %d/%d)",
                    exc.response.status_code,
                    repository,
                    commit_hash[:8] if commit_hash else "",
                    attempt,
                    _MAX_RETRIES + 1,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Bitbucket API network error for %s@%s (attempt %d/%d): %s",
                    repository,
                    commit_hash[:8] if commit_hash else "",
                    attempt,
                    _MAX_RETRIES + 1,
                    str(exc),
                )

        msg = f"Bitbucket API call failed after {_MAX_RETRIES + 1} attempts: {last_error}"
        raise GitProviderAPIError(msg, repository=repository)


def _parse_commit_detail(repository: str, data: dict[str, Any]) -> GitCommitDetail:
    """Parse Bitbucket commit API response to GitCommitDetail."""
    author_data = data.get("author", {})
    committed_at = None
    raw_date = data.get("date")
    if raw_date:
        with contextlib.suppress(ValueError, TypeError):
            committed_at = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).astimezone(UTC)

    # Bitbucket uses "raw" field for author name + email: "John Doe <john@example.com>"
    raw_author = author_data.get("raw", "")
    author_name = raw_author.split("<")[0].strip() if "<" in raw_author else raw_author
    if not author_name and author_data.get("user"):
        author_name = author_data["user"].get("display_name")

    return GitCommitDetail(
        repository=repository,
        hash=data.get("hash", ""),
        author=author_name or None,
        message=data.get("message"),
        committed_at=committed_at,
        url=data.get("links", {}).get("html", {}).get("href"),
    )


def _parse_pull_requests(repository: str, data: dict[str, Any]) -> list[GitPullRequestDetail]:
    """Parse Bitbucket pull request search response."""
    values = data.get("values", [])
    results: list[GitPullRequestDetail] = []

    for pr_data in values:
        merge_timestamp = None
        if pr_data.get("updated_on") and pr_data.get("state") == "MERGED":
            with contextlib.suppress(ValueError, TypeError):
                merge_timestamp = datetime.fromisoformat(str(pr_data["updated_on"]).replace("Z", "+00:00")).astimezone(
                    UTC
                )

        author_data = pr_data.get("author", {})
        results.append(
            GitPullRequestDetail(
                external_id=str(pr_data.get("id", "")),
                repository=repository,
                title=pr_data.get("title"),
                author=author_data.get("display_name"),
                source_branch=(pr_data.get("source", {}).get("branch") or {}).get("name"),
                target_branch=(pr_data.get("destination", {}).get("branch") or {}).get("name"),
                merge_timestamp=merge_timestamp,
                url=pr_data.get("links", {}).get("html", {}).get("href"),
            )
        )

    return results


__all__ = [
    "BitbucketProvider",
]
