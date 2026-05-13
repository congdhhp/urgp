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

    token = _resolve_token(git_config)
    if token is None:
        return None

    provider_type = str(git_config.get("provider", default_provider)).lower()
    api_base_url = _resolve_string(git_config, "api_base_url", "base_url")
    kwargs: dict[str, Any] = {"cache": cache}
    if api_base_url is not None:
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
