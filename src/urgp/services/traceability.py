"""Traceability hydrator for commits, pull requests, and issues.

Constructs the traceability graph by combining payload-supplied metadata
with enrichment from external Git provider and Issue tracker APIs.

Reference: docs/05-technical-design.md § Traceability Hydrator
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from urgp.config import URGPSettings
from urgp.integrations.git.base import GitCommitDetail, GitProvider, GitProviderAPIError, GitPullRequestDetail
from urgp.integrations.issues.base import IssueTracker, IssueTrackerAPIError
from urgp.models.manifest import BuildManifest
from urgp.models.traceability import Commit, Issue, PullRequest, commit_issues, commit_prs
from urgp.schemas.ingest import CommitHashSchema, IngestPayload

logger = logging.getLogger(__name__)

_HYDRATION_SLA_SECONDS = 30.0
_PER_CALL_TIMEOUT = 5.0


@dataclass(frozen=True)
class HydrationResult:
    commit_count: int
    pull_request_count: int
    issue_count: int
    traceability_incomplete: bool


class TraceabilityHydrator:
    """Populate the traceability graph from payload data + external APIs.

    When git_provider or issue_tracker is provided, the hydrator enriches
    commit metadata, discovers pull requests, and resolves issue details
    by calling external APIs concurrently via asyncio.

    When no external providers are configured, falls back to payload-only
    hydration (the original behavior).
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: URGPSettings,
        *,
        git_provider: GitProvider | None = None,
        issue_tracker: IssueTracker | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._git_provider = git_provider
        self._issue_tracker = issue_tracker

    async def hydrate(self, manifest: BuildManifest, payload: IngestPayload) -> HydrationResult:
        """Build the traceability graph with SLA-bounded external enrichment."""
        issue_regex = self._resolve_issue_pattern(manifest)
        traceability_incomplete = False
        pull_request_ids: set[tuple[str, str]] = set()
        issue_ids: set[tuple[str, str]] = set()

        # Step 1: Enrich commits from external Git provider (concurrent)
        enriched_commits = await self._enrich_commits_from_provider(payload.commit_hashes)

        for commit_payload in payload.commit_hashes:
            commit = await self._load_commit(commit_payload)
            if commit is None:
                traceability_incomplete = True
                continue

            # Merge payload data with enriched data from Git API
            enriched = enriched_commits.get((commit_payload.repository, commit_payload.hash))
            self._update_commit_metadata(commit, commit_payload, enriched)

            # Step 2: Attach pull requests (from payload + Git API)
            attached_pull_request = False

            # Pull requests from payload
            if commit_payload.pull_request is not None:
                pr = await self._ensure_pull_request_from_payload(commit_payload)
                await self._session.execute(
                    insert(commit_prs).values(commit_id=commit.id, pr_id=pr.id).on_conflict_do_nothing()
                )
                pull_request_ids.add((pr.repository, pr.external_id))
                attached_pull_request = True

            # Pull requests from Git API
            api_prs = await self._find_pull_requests_from_provider(commit_payload.repository, commit_payload.hash)
            for api_pr in api_prs:
                pr = await self._ensure_pull_request_from_api(api_pr)
                await self._session.execute(
                    insert(commit_prs).values(commit_id=commit.id, pr_id=pr.id).on_conflict_do_nothing()
                )
                pull_request_ids.add((pr.repository, pr.external_id))
                attached_pull_request = True

            # Step 3: Extract and resolve issues
            extracted_issue_ids = self._extract_issue_ids(commit_payload, issue_regex)
            if extracted_issue_ids:
                # Enrich issues from Issue Tracker API
                enriched_issues = await self._enrich_issues_from_tracker(manifest, extracted_issue_ids)
                for issue_external_id in extracted_issue_ids:
                    issue = await self._ensure_issue(manifest, issue_external_id, enriched_issues)
                    await self._session.execute(
                        insert(commit_issues).values(commit_id=commit.id, issue_id=issue.id).on_conflict_do_nothing()
                    )
                    issue_ids.add((issue.tracker_type, issue.external_id))
            elif not attached_pull_request:
                traceability_incomplete = True

        return HydrationResult(
            commit_count=len(payload.commit_hashes),
            pull_request_count=len(pull_request_ids),
            issue_count=len(issue_ids),
            traceability_incomplete=traceability_incomplete,
        )

    # ─────────────────────────────────────────────
    # External API Enrichment (Git Provider)
    # ─────────────────────────────────────────────

    async def _enrich_commits_from_provider(
        self, commit_payloads: list[CommitHashSchema]
    ) -> dict[tuple[str, str], GitCommitDetail]:
        """Concurrently enrich all commits from the Git provider API."""
        if self._git_provider is None:
            return {}

        results: dict[tuple[str, str], GitCommitDetail] = {}

        async def _fetch_one(payload: CommitHashSchema) -> None:
            try:
                detail = await asyncio.wait_for(
                    self._git_provider.get_commit(payload.repository, payload.hash),  # type: ignore[union-attr]
                    timeout=_PER_CALL_TIMEOUT,
                )
                results[(payload.repository, payload.hash)] = detail
            except (GitProviderAPIError, TimeoutError):
                logger.warning(
                    "Git API enrichment failed for %s@%s; using payload data",
                    payload.repository,
                    payload.hash[:8],
                    exc_info=True,
                )

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_fetch_one(p) for p in commit_payloads], return_exceptions=True),
                timeout=_HYDRATION_SLA_SECONDS / 2,
            )
        except TimeoutError:
            logger.warning("Git enrichment exceeded SLA budget; proceeding with partial data")

        return results

    async def _find_pull_requests_from_provider(self, repository: str, commit_hash: str) -> list[GitPullRequestDetail]:
        """Find PRs for a commit from the Git provider (with timeout)."""
        if self._git_provider is None:
            return []

        try:
            return await asyncio.wait_for(
                self._git_provider.find_pull_requests(repository, commit_hash),
                timeout=_PER_CALL_TIMEOUT,
            )
        except (GitProviderAPIError, TimeoutError):
            logger.warning(
                "Git API PR lookup failed for %s@%s",
                repository,
                commit_hash[:8],
                exc_info=True,
            )
            return []

    # ─────────────────────────────────────────────
    # External API Enrichment (Issue Tracker)
    # ─────────────────────────────────────────────

    async def _enrich_issues_from_tracker(self, manifest: BuildManifest, issue_ids: set[str]) -> dict[str, object]:
        """Batch-fetch issue details from the issue tracker API."""
        if self._issue_tracker is None:
            return {}

        try:
            result = await asyncio.wait_for(
                self._issue_tracker.batch_get(issue_ids),
                timeout=_HYDRATION_SLA_SECONDS / 2,
            )
            return cast(dict[str, object], result)
        except (IssueTrackerAPIError, TimeoutError):
            logger.warning(
                "Issue tracker batch query failed for %d issues; using stub data",
                len(issue_ids),
                exc_info=True,
            )
            return {}

    # ─────────────────────────────────────────────
    # Commit/PR/Issue persistence helpers
    # ─────────────────────────────────────────────

    async def _load_commit(self, payload: CommitHashSchema) -> Commit | None:
        return cast(
            Commit | None,
            await self._session.scalar(
                select(Commit).where(
                    Commit.repository == payload.repository,
                    Commit.hash == payload.hash,
                )
            ),
        )

    def _update_commit_metadata(
        self,
        commit: Commit,
        payload: CommitHashSchema,
        enriched: GitCommitDetail | None = None,
    ) -> None:
        """Merge payload data and API-enriched data into the commit record.

        Priority: explicit payload values > API-enriched values > existing DB values.
        """
        commit.branch = payload.branch or (enriched.branch if enriched else None) or commit.branch
        commit.author = payload.author or (enriched.author if enriched else None) or commit.author
        commit.message = payload.message or (enriched.message if enriched else None) or commit.message
        commit.committed_at = (
            payload.committed_at or (enriched.committed_at if enriched else None) or commit.committed_at
        )

    async def _ensure_pull_request_from_payload(self, payload: CommitHashSchema) -> PullRequest:
        """Create or update a PR from payload-supplied data."""
        assert payload.pull_request is not None
        pull_request = await self._session.scalar(
            select(PullRequest).where(
                PullRequest.repository == payload.repository,
                PullRequest.external_id == payload.pull_request.external_id,
            )
        )
        if pull_request is None:
            pull_request = PullRequest(
                repository=payload.repository,
                external_id=payload.pull_request.external_id,
                title=payload.pull_request.title,
                author=payload.pull_request.author,
                source_branch=payload.pull_request.source_branch,
                target_branch=payload.pull_request.target_branch,
                merge_timestamp=payload.pull_request.merge_timestamp,
                url=payload.pull_request.url,
            )
            self._session.add(pull_request)
            await self._session.flush()
            return pull_request

        pull_request.title = payload.pull_request.title or pull_request.title
        pull_request.author = payload.pull_request.author or pull_request.author
        pull_request.source_branch = payload.pull_request.source_branch or pull_request.source_branch
        pull_request.target_branch = payload.pull_request.target_branch or pull_request.target_branch
        pull_request.merge_timestamp = payload.pull_request.merge_timestamp or pull_request.merge_timestamp
        pull_request.url = payload.pull_request.url or pull_request.url
        return pull_request

    async def _ensure_pull_request_from_api(self, api_pr: GitPullRequestDetail) -> PullRequest:
        """Create or update a PR from Git API-resolved data."""
        pull_request = await self._session.scalar(
            select(PullRequest).where(
                PullRequest.repository == api_pr.repository,
                PullRequest.external_id == api_pr.external_id,
            )
        )
        if pull_request is None:
            pull_request = PullRequest(
                repository=api_pr.repository,
                external_id=api_pr.external_id,
                title=api_pr.title,
                author=api_pr.author,
                source_branch=api_pr.source_branch,
                target_branch=api_pr.target_branch,
                merge_timestamp=api_pr.merge_timestamp,
                url=api_pr.url,
            )
            self._session.add(pull_request)
            await self._session.flush()
            return pull_request

        pull_request.title = api_pr.title or pull_request.title
        pull_request.author = api_pr.author or pull_request.author
        pull_request.source_branch = api_pr.source_branch or pull_request.source_branch
        pull_request.target_branch = api_pr.target_branch or pull_request.target_branch
        pull_request.merge_timestamp = api_pr.merge_timestamp or pull_request.merge_timestamp
        pull_request.url = api_pr.url or pull_request.url
        return pull_request

    async def _ensure_issue(
        self,
        manifest: BuildManifest,
        external_id: str,
        enriched_issues: dict[str, object] | None = None,
    ) -> Issue:
        """Create or update an issue, enriching with tracker API data if available."""
        tracker_type = self._resolve_issue_tracker(manifest)
        issue = await self._session.scalar(
            select(Issue).where(
                Issue.external_id == external_id,
                Issue.tracker_type == tracker_type,
            )
        )

        # Get enriched data if available
        enriched = None
        if enriched_issues and external_id in enriched_issues:
            enriched = enriched_issues[external_id]

        if issue is not None:
            # Update with enriched data if the issue already exists
            if enriched is not None and hasattr(enriched, "title"):
                issue.title = getattr(enriched, "title", None) or issue.title
                issue.status = getattr(enriched, "status", None) or issue.status
                issue.priority = getattr(enriched, "priority", None) or issue.priority
                issue.assignee = getattr(enriched, "assignee", None) or issue.assignee
                labels = getattr(enriched, "labels", None)
                if labels is not None:
                    issue.labels = labels if isinstance(labels, dict) else {"items": labels}
                issue.url = getattr(enriched, "url", None) or issue.url
            return issue

        # Create new issue
        title = None
        status = None
        priority = None
        assignee = None
        labels_val = None
        url = None
        if enriched is not None and hasattr(enriched, "title"):
            title = getattr(enriched, "title", None)
            status = getattr(enriched, "status", None)
            priority = getattr(enriched, "priority", None)
            assignee = getattr(enriched, "assignee", None)
            raw_labels = getattr(enriched, "labels", None)
            labels_val = raw_labels if isinstance(raw_labels, dict) else ({"items": raw_labels} if raw_labels else None)
            url = getattr(enriched, "url", None)

        issue = Issue(
            external_id=external_id,
            tracker_type=tracker_type,
            title=title,
            status=status,
            priority=priority,
            assignee=assignee,
            labels=labels_val,
            url=url,
        )
        self._session.add(issue)
        await self._session.flush()
        return issue

    def _extract_issue_ids(self, payload: CommitHashSchema, issue_pattern: re.Pattern[str]) -> set[str]:
        explicit_issue_ids = set(payload.issue_ids or [])
        searchable_fields = [value for value in (payload.message, payload.branch) if value]
        inferred_issue_ids = {match.group(0) for field in searchable_fields for match in issue_pattern.finditer(field)}
        return explicit_issue_ids | inferred_issue_ids

    def _resolve_issue_pattern(self, manifest: BuildManifest) -> re.Pattern[str]:
        issue_config = manifest.product.issue_config or {}
        pattern_value = issue_config.get("issue_regex")
        if isinstance(pattern_value, str) and pattern_value.strip():
            return re.compile(pattern_value)
        return re.compile(self._settings.default_issue_regex)

    def _resolve_issue_tracker(self, manifest: BuildManifest) -> str:
        issue_config = manifest.product.issue_config or {}
        tracker_value = issue_config.get("tracker")
        if isinstance(tracker_value, str) and tracker_value.strip():
            return tracker_value
        return self._settings.default_issue_tracker


__all__ = [
    "HydrationResult",
    "TraceabilityHydrator",
]
