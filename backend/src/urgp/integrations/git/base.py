"""Abstract Git provider interface for traceability hydration.

Reference: docs/05-technical-design.md § Git Provider Adapter Interface
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitCommitDetail:
    """Resolved commit metadata from a Git provider API."""

    repository: str
    hash: str
    author: str | None = None
    message: str | None = None
    branch: str | None = None
    committed_at: datetime | None = None
    url: str | None = None


@dataclass(frozen=True)
class GitPullRequestDetail:
    """Pull request metadata from a Git provider API."""

    external_id: str
    repository: str
    title: str | None = None
    author: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    merge_timestamp: datetime | None = None
    url: str | None = None


@dataclass(frozen=True)
class GitProviderError:
    """Non-fatal error that occurred during a Git provider API call."""

    repository: str
    commit_hash: str
    error: str
    status_code: int | None = None


@dataclass
class GitResolutionResult:
    """Aggregated result of resolving commits and PRs from a Git provider."""

    commits: list[GitCommitDetail] = field(default_factory=list)
    pull_requests: list[GitPullRequestDetail] = field(default_factory=list)
    errors: list[GitProviderError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class GitProvider(ABC):
    """Abstract base class for Git provider integrations.

    Implementations must handle:
    - API rate limiting (respect Retry-After headers)
    - Redis caching (5-min TTL)
    - Graceful error handling (return partial results)
    """

    @abstractmethod
    async def get_commit(self, repository: str, commit_hash: str) -> GitCommitDetail:
        """Resolve a commit hash to full commit metadata.

        Args:
            repository: Full repository identifier (e.g., 'org/repo')
            commit_hash: 40-character SHA-1 hex string

        Returns:
            GitCommitDetail with resolved metadata

        Raises:
            GitProviderAPIError: If the API call fails after retries
        """
        ...

    @abstractmethod
    async def find_pull_requests(self, repository: str, commit_hash: str) -> list[GitPullRequestDetail]:
        """Find pull requests associated with a commit.

        Args:
            repository: Full repository identifier
            commit_hash: 40-character SHA-1 hex string

        Returns:
            List of associated pull requests (may be empty)

        Raises:
            GitProviderAPIError: If the API call fails after retries
        """
        ...

    @abstractmethod
    async def test_connection(self, repository: str) -> bool:
        """Test connectivity and credentials by making a lightweight API call.

        Args:
            repository: Repository identifier to test against

        Returns:
            True if connection is successful
        """
        ...


class GitProviderAPIError(Exception):
    """Raised when a Git provider API call fails after retries."""

    def __init__(self, message: str, *, status_code: int | None = None, repository: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.repository = repository


__all__ = [
    "GitCommitDetail",
    "GitProvider",
    "GitProviderAPIError",
    "GitProviderError",
    "GitPullRequestDetail",
    "GitResolutionResult",
]
