"""Traceability hydrator for commits, pull requests, and issues."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from urgp.config import URGPSettings
from urgp.models.manifest import BuildManifest
from urgp.models.traceability import Commit, Issue, PullRequest, commit_issues, commit_prs
from urgp.schemas.ingest import CommitHashSchema, IngestPayload


@dataclass(frozen=True)
class HydrationResult:
    commit_count: int
    pull_request_count: int
    issue_count: int
    traceability_incomplete: bool


class TraceabilityHydrator:
    """Populate the traceability graph from payload-supplied metadata."""

    def __init__(self, session: AsyncSession, settings: URGPSettings) -> None:
        self._session = session
        self._settings = settings

    async def hydrate(self, manifest: BuildManifest, payload: IngestPayload) -> HydrationResult:
        issue_regex = self._resolve_issue_pattern(manifest)
        traceability_incomplete = False
        pull_request_ids: set[tuple[str, str]] = set()
        issue_ids: set[tuple[str, str]] = set()

        for commit_payload in payload.commit_hashes:
            commit = await self._load_commit(commit_payload)
            if commit is None:
                traceability_incomplete = True
                continue

            self._update_commit_metadata(commit, commit_payload)
            attached_pull_request = False
            if commit_payload.pull_request is not None:
                pr = await self._ensure_pull_request(commit_payload)
                await self._session.execute(
                    insert(commit_prs)
                    .values(commit_id=commit.id, pr_id=pr.id)
                    .on_conflict_do_nothing()
                )
                pull_request_ids.add((pr.repository, pr.external_id))
                attached_pull_request = True

            extracted_issue_ids = self._extract_issue_ids(commit_payload, issue_regex)
            if extracted_issue_ids:
                for issue_external_id in extracted_issue_ids:
                    issue = await self._ensure_issue(manifest, issue_external_id)
                    await self._session.execute(
                        insert(commit_issues)
                        .values(commit_id=commit.id, issue_id=issue.id)
                        .on_conflict_do_nothing()
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

    def _update_commit_metadata(self, commit: Commit, payload: CommitHashSchema) -> None:
        if payload.branch is not None:
            commit.branch = payload.branch
        if payload.author is not None:
            commit.author = payload.author
        if payload.message is not None:
            commit.message = payload.message
        if payload.committed_at is not None:
            commit.committed_at = payload.committed_at

    async def _ensure_pull_request(self, payload: CommitHashSchema) -> PullRequest:
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

    async def _ensure_issue(self, manifest: BuildManifest, external_id: str) -> Issue:
        tracker_type = self._resolve_issue_tracker(manifest)
        issue = await self._session.scalar(
            select(Issue).where(
                Issue.external_id == external_id,
                Issue.tracker_type == tracker_type,
            )
        )
        if issue is not None:
            return issue

        issue = Issue(
            external_id=external_id,
            tracker_type=tracker_type,
            title=None,
            status=None,
            priority=None,
            assignee=None,
            labels=None,
            url=None,
        )
        self._session.add(issue)
        await self._session.flush()
        return issue

    def _extract_issue_ids(self, payload: CommitHashSchema, issue_pattern: re.Pattern[str]) -> set[str]:
        explicit_issue_ids = set(payload.issue_ids or [])
        searchable_fields = [value for value in (payload.message, payload.branch) if value]
        inferred_issue_ids = {
            match.group(0)
            for field in searchable_fields
            for match in issue_pattern.finditer(field)
        }
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
