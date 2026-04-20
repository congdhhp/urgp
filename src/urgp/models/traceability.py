"""Traceability models — Commits, Pull Requests, Issues, and junction tables.

Reference: docs/05-technical-design.md § Data Model (commits, pull_requests, issues, junction tables)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from urgp.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from urgp.models.manifest import BuildManifest


# ─────────────────────────────────────────────
# Junction Tables (Many-to-Many)
# ─────────────────────────────────────────────

build_commits = Table(
    "build_commits",
    Base.metadata,
    Column("build_id", UUID(as_uuid=True), ForeignKey("build_manifests.id", ondelete="CASCADE"), primary_key=True),
    Column("commit_id", UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"), primary_key=True),
)

commit_prs = Table(
    "commit_prs",
    Base.metadata,
    Column("commit_id", UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"), primary_key=True),
    Column("pr_id", UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), primary_key=True),
)

commit_issues = Table(
    "commit_issues",
    Base.metadata,
    Column("commit_id", UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"), primary_key=True),
    Column("issue_id", UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True),
)


# ─────────────────────────────────────────────
# ORM Models
# ─────────────────────────────────────────────


class Commit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Commit entity.

    Represents a single Git commit with its metadata.
    Linked to builds via build_commits junction table.
    """

    __tablename__ = "commits"
    __table_args__ = (Index("ix_commits_hash", "hash", unique=True),)

    hash: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)  # SHA-1 hex
    repository: Mapped[str] = mapped_column(String(500), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    manifests: Mapped[list[BuildManifest]] = relationship(
        "BuildManifest", secondary=build_commits, back_populates="commits"
    )
    pull_requests: Mapped[list[PullRequest]] = relationship(
        "PullRequest", secondary=commit_prs, back_populates="commits"
    )
    issues: Mapped[list[Issue]] = relationship("Issue", secondary=commit_issues, back_populates="commits")

    def __repr__(self) -> str:
        return f"<Commit(hash='{self.hash[:8]}...', repo='{self.repository}')>"


class PullRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pull Request entity.

    Represents a pull/merge request from a Git provider.
    """

    __tablename__ = "pull_requests"

    external_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "456" or "PR-456"
    repository: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merge_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    commits: Mapped[list[Commit]] = relationship("Commit", secondary=commit_prs, back_populates="pull_requests")

    def __repr__(self) -> str:
        return f"<PullRequest(external_id='{self.external_id}', repo='{self.repository}')>"


class Issue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Issue/Work Item entity.

    Represents a Jira issue (or similar tracker item).
    """

    __tablename__ = "issues"

    external_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "PROJ-1234"
    tracker_type: Mapped[str] = mapped_column(String(50), nullable=False, default="jira")  # jira, github, azure
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Critical, Major, Normal, Minor
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    labels: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)  # Array of label strings
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    commits: Mapped[list[Commit]] = relationship("Commit", secondary=commit_issues, back_populates="issues")

    def __repr__(self) -> str:
        return f"<Issue(external_id='{self.external_id}', tracker='{self.tracker_type}')>"
