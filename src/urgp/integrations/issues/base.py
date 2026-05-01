"""Abstract Issue Tracker interface for traceability hydration.

Reference: docs/05-technical-design.md § Issue Tracker Adapter Interface
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IssueDetail:
    """Resolved issue metadata from an issue tracker API."""

    external_id: str
    tracker_type: str
    title: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    labels: list[str] | None = None
    url: str | None = None


class IssueTracker(ABC):
    """Abstract base class for issue tracker integrations.

    Implementations must handle:
    - Batch queries (chunk large ID lists into API-safe batches)
    - Redis caching (5-min TTL)
    - Missing issues (log warning, continue processing)
    """

    @abstractmethod
    async def get_issue(self, issue_id: str) -> IssueDetail | None:
        """Retrieve a single issue by its external identifier.

        Args:
            issue_id: Issue identifier (e.g., 'PROJ-1234')

        Returns:
            IssueDetail if found, None if the issue does not exist.

        Raises:
            IssueTrackerAPIError: If the API call fails after retries
        """
        ...

    @abstractmethod
    async def batch_get(self, issue_ids: set[str]) -> dict[str, IssueDetail]:
        """Retrieve multiple issues in a batch.

        Args:
            issue_ids: Set of issue identifiers to resolve

        Returns:
            Mapping of issue_id -> IssueDetail for found issues.
            Missing issues are omitted (not raised as errors).
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connectivity and credentials.

        Returns:
            True if connection is successful
        """
        ...


class IssueTrackerAPIError(Exception):
    """Raised when an issue tracker API call fails after retries."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


__all__ = [
    "IssueDetail",
    "IssueTracker",
    "IssueTrackerAPIError",
]
