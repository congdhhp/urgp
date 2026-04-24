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

    token = issue_config.get("token")
    if not isinstance(token, str) or not token.strip():
        return None

    api_base_url = issue_config.get("api_base_url")
    if not isinstance(api_base_url, str) or not api_base_url.strip():
        return None

    tracker_type = str(issue_config.get("tracker", default_tracker)).lower()

    if tracker_type == "jira":
        email = issue_config.get("email", "")
        return JiraTracker(
            api_base_url,
            email=str(email) if email else "",
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
