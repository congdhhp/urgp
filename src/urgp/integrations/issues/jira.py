"""Jira REST API v3 issue tracker adapter.

Resolves Jira issues by key using JQL search for efficient batch retrieval.

Reference:
- POST /rest/api/3/search (JQL: key in (PROJ-123, PROJ-456))
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from urgp.integrations.issues.base import IssueDetail, IssueTracker, IssueTrackerAPIError
from urgp.services.cache import CacheService

logger = logging.getLogger(__name__)

_API_TIMEOUT = 10.0
_MAX_RETRIES = 2
_BATCH_SIZE = 50  # Jira JQL `key in (...)` max practical batch size


class JiraTracker(IssueTracker):
    """Jira REST API v3 adapter for issue resolution and batch retrieval."""

    def __init__(
        self,
        api_base_url: str,
        *,
        email: str = "",
        token: str,
        cache: CacheService | None = None,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._email = email
        self._token = token
        self._cache = cache

    async def get_issue(self, issue_id: str) -> IssueDetail | None:
        """Retrieve a single Jira issue by key."""
        cache_key = f"jira:issue:{issue_id}"

        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                logger.debug("Cache hit for issue %s", issue_id)
                return _parse_issue(cached)

        try:
            url = f"{self._api_base_url}/rest/api/3/issue/{issue_id}"
            data = await self._api_get(url)
        except IssueTrackerAPIError as exc:
            if exc.status_code == 404:
                logger.warning("Jira issue %s not found; skipping", issue_id)
                return None
            raise

        if self._cache is not None:
            await self._cache.set_json(cache_key, data)

        return _parse_issue(data)

    async def batch_get(self, issue_ids: set[str]) -> dict[str, IssueDetail]:
        """Retrieve multiple issues via JQL search, chunked into batches."""
        if not issue_ids:
            return {}

        results: dict[str, IssueDetail] = {}

        # Check cache first, collect misses
        uncached_ids: list[str] = []
        for issue_id in issue_ids:
            if self._cache is not None:
                cached = await self._cache.get_json(f"jira:issue:{issue_id}")
                if cached is not None:
                    detail = _parse_issue(cached)
                    if detail is not None:
                        results[issue_id] = detail
                        continue
            uncached_ids.append(issue_id)

        # Batch-fetch uncached issues via JQL
        for chunk_start in range(0, len(uncached_ids), _BATCH_SIZE):
            chunk = uncached_ids[chunk_start : chunk_start + _BATCH_SIZE]
            try:
                fetched = await self._jql_search(chunk)
                for issue_data in fetched:
                    detail = _parse_issue(issue_data)
                    if detail is not None:
                        results[detail.external_id] = detail
                        if self._cache is not None:
                            await self._cache.set_json(f"jira:issue:{detail.external_id}", issue_data)
            except IssueTrackerAPIError:
                # Log and continue — partial results are acceptable
                logger.warning("Jira batch query failed for chunk of %d issues; skipping", len(chunk), exc_info=True)

        return results

    async def test_connection(self) -> bool:
        """Test Jira API connectivity by fetching server info."""
        try:
            url = f"{self._api_base_url}/rest/api/3/serverInfo"
            await self._api_get(url)
            return True
        except IssueTrackerAPIError:
            return False

    async def _jql_search(self, issue_keys: list[str]) -> list[dict[str, Any]]:
        """Execute a JQL search for the given issue keys."""
        jql = f"key in ({','.join(issue_keys)})"
        url = f"{self._api_base_url}/rest/api/3/search"
        payload = {
            "jql": jql,
            "maxResults": len(issue_keys),
            "fields": ["summary", "status", "priority", "assignee", "labels", "issuetype"],
        }

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                    response = await client.post(url, json=payload, headers=self._build_headers())

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(
                        "Jira rate limit exceeded; Retry-After=%s (attempt %d/%d)",
                        retry_after,
                        attempt,
                        _MAX_RETRIES + 1,
                    )
                    import asyncio

                    await asyncio.sleep(min(float(retry_after), 30.0))
                    continue

                response.raise_for_status()
                data = response.json()
                issues: list[dict[str, Any]] = data.get("issues", [])
                return issues

            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "Jira search API error %d (attempt %d/%d)",
                    exc.response.status_code,
                    attempt,
                    _MAX_RETRIES + 1,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Jira search API network error (attempt %d/%d): %s",
                    attempt,
                    _MAX_RETRIES + 1,
                    str(exc),
                )

        msg = f"Jira JQL search failed after {_MAX_RETRIES + 1} attempts: {last_error}"
        raise IssueTrackerAPIError(msg)

    async def _api_get(self, url: str) -> Any:
        """Execute a GET request with retry."""
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                    response = await client.get(url, headers=self._build_headers())

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    import asyncio

                    await asyncio.sleep(min(float(retry_after), 30.0))
                    continue

                if response.status_code == 404:
                    msg = f"Jira resource not found: {url}"
                    raise IssueTrackerAPIError(msg, status_code=404)

                response.raise_for_status()
                return response.json()

            except IssueTrackerAPIError:
                raise
            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "Jira API error %d (attempt %d/%d)",
                    exc.response.status_code,
                    attempt,
                    _MAX_RETRIES + 1,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Jira API network error (attempt %d/%d): %s",
                    attempt,
                    _MAX_RETRIES + 1,
                    str(exc),
                )

        msg = f"Jira API call failed after {_MAX_RETRIES + 1} attempts: {last_error}"
        raise IssueTrackerAPIError(msg)

    def _build_headers(self) -> dict[str, str]:
        """Build authentication headers for Jira Cloud (API token + email)."""
        import base64

        if self._email:
            credentials = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
            return {
                "Authorization": f"Basic {credentials}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


def _parse_issue(data: dict[str, Any]) -> IssueDetail | None:
    """Parse a Jira issue JSON response into IssueDetail."""
    key = data.get("key")
    if not key:
        return None

    fields = data.get("fields", {})
    status_data = fields.get("status", {})
    priority_data = fields.get("priority", {})
    assignee_data = fields.get("assignee", {})

    labels_raw = fields.get("labels")
    labels = list(labels_raw) if isinstance(labels_raw, list) else None

    # Build URL from self link
    self_link = data.get("self", "")
    browse_url = None
    if self_link:
        # Convert REST URL to browse URL: https://jira.example.com/rest/api/3/issue/PROJ-123
        # → https://jira.example.com/browse/PROJ-123
        base = self_link.split("/rest/")[0] if "/rest/" in self_link else ""
        if base:
            browse_url = f"{base}/browse/{key}"

    return IssueDetail(
        external_id=key,
        tracker_type="jira",
        title=fields.get("summary"),
        status=status_data.get("name") if status_data else None,
        priority=priority_data.get("name") if priority_data else None,
        assignee=assignee_data.get("displayName") if assignee_data else None,
        labels=labels,
        url=browse_url,
    )


__all__ = [
    "JiraTracker",
]
