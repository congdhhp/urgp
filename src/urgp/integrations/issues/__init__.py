"""URGP Issue tracker integrations.

Factory function creates tracker instances from product-level configuration.

Supported trackers:
- jira: Jira Cloud/Server REST API v3
"""

from __future__ import annotations

from typing import Any

from urgp.integrations.issues.base import (
    IssueDetail,
    IssueTracker,
    IssueTrackerAPIError,
)
from urgp.integrations.issues.jira import JiraTracker
from urgp.services.cache import CacheService


def _resolve_string(config: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_token(config: dict[str, Any]) -> str | None:
    token = _resolve_string(config, "token", "authentication_token")
    if token is not None:
        return token

    credentials = config.get("credentials")
    if isinstance(credentials, dict):
        return _resolve_string(credentials, "token", "authentication_token")
    return None


def create_issue_tracker(
    issue_config: dict[str, Any] | None,
    *,
    cache: CacheService | None = None,
    default_tracker: str = "jira",
) -> IssueTracker | None:
    """Create an issue tracker from product-level configuration.

    Args:
        issue_config: Product.issue_config JSONB value containing tracker type and credentials.
            Expected keys: 'tracker' (str), 'token' (str), 'api_base_url' (str),
            optionally 'email' (str, for Jira Cloud basic auth).
        cache: Optional cache service for API response caching.
        default_tracker: Default tracker type if not specified in config.

    Returns:
        Configured IssueTracker instance, or None if config is missing/invalid.
    """
    if issue_config is None:
        return None

    token = _resolve_token(issue_config)
    if token is None:
        return None

    api_base_url = _resolve_string(issue_config, "api_base_url", "base_url")
    if api_base_url is None:
        return None

    tracker_type = str(issue_config.get("tracker", default_tracker)).lower()

    if tracker_type == "jira":
        email = _resolve_string(issue_config, "email")
        credentials = issue_config.get("credentials")
        if email is None and isinstance(credentials, dict):
            email = _resolve_string(credentials, "email")
        return JiraTracker(
            api_base_url,
            email=email or "",
            token=token,
            cache=cache,
        )

    return None


__all__ = [
    "IssueDetail",
    "IssueTracker",
    "IssueTrackerAPIError",
    "JiraTracker",
    "create_issue_tracker",
]
