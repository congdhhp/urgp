"""URGP Git provider integrations.

Factory function creates provider instances from product-level configuration.

Supported providers:
- github: GitHub REST API v3
- bitbucket: Bitbucket Cloud REST API v2
"""

from __future__ import annotations

from typing import Any

from urgp.integrations.git.base import (
    GitCommitDetail,
    GitProvider,
    GitProviderAPIError,
    GitProviderError,
    GitPullRequestDetail,
    GitResolutionResult,
)
from urgp.integrations.git.bitbucket import BitbucketProvider
from urgp.integrations.git.github import GitHubProvider
from urgp.services.cache import CacheService


def create_git_provider(
    git_config: dict[str, Any] | None,
    *,
    cache: CacheService | None = None,
    default_provider: str = "github",
) -> GitProvider | None:
    """Create a Git provider from product-level configuration.

    Args:
        git_config: Product.git_config JSONB value containing provider type and credentials.
            Expected keys: 'provider' (str), 'token' (str), optionally 'api_base_url' (str).
        cache: Optional cache service for API response caching.
        default_provider: Default provider type if not specified in config.

    Returns:
        Configured GitProvider instance, or None if config is missing/invalid.
    """
    if git_config is None:
        return None

    token = git_config.get("token")
    if not isinstance(token, str) or not token.strip():
        return None

    provider_type = str(git_config.get("provider", default_provider)).lower()
    api_base_url = git_config.get("api_base_url")
    kwargs: dict[str, Any] = {"cache": cache}
    if isinstance(api_base_url, str) and api_base_url.strip():
        kwargs["api_base_url"] = api_base_url

    if provider_type == "github":
        return GitHubProvider(token, **kwargs)
    if provider_type == "bitbucket":
        return BitbucketProvider(token, **kwargs)

    return None


__all__ = [
    "BitbucketProvider",
    "GitCommitDetail",
    "GitHubProvider",
    "GitProvider",
    "GitProviderAPIError",
    "GitProviderError",
    "GitPullRequestDetail",
    "GitResolutionResult",
    "create_git_provider",
]
