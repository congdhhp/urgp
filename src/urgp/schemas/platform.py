"""Schemas for platform-grade APIs: catalog, builds, activity, and notifications."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from urgp.models.enums import ArtifactType, BuildStatus, BuildType, NotificationChannel


class ProductCreateRequest(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    git_config: dict[str, object] | None = None
    issue_config: dict[str, object] | None = None


class ReleaseCreateRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=100)
    release_type: str | None = Field(default=None, max_length=50)
    status: str = Field(default="active", min_length=1, max_length=50)


class ProductSummaryResponse(BaseModel):
    external_id: str
    name: str
    description: str | None = None
    release_count: int = 0
    build_count: int = 0
    last_build_id: str | None = None
    last_build_status: BuildStatus | None = None
    last_build_at: datetime | None = None


class ReleaseSummaryResponse(BaseModel):
    version: str
    release_type: str | None = None
    status: str
    build_count: int = 0
    last_build_id: str | None = None
    last_build_status: BuildStatus | None = None
    last_build_at: datetime | None = None


class ProductListResponse(BaseModel):
    items: list[ProductSummaryResponse]
    total: int


class ReleaseListResponse(BaseModel):
    product_id: str
    product_name: str
    items: list[ReleaseSummaryResponse]
    total: int


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: ArtifactType
    storage_uri: str
    sha256: str = Field(alias="sha256_checksum")
    size_bytes: int | None = None
    metadata: dict[str, object] | None = Field(default=None, alias="metadata_")

    model_config = {"populate_by_name": True}


class PullRequestResponse(BaseModel):
    external_id: str
    title: str | None = None
    author: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    merge_timestamp: datetime | None = None
    url: str | None = None


class IssueResponse(BaseModel):
    external_id: str
    tracker_type: str
    title: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    labels: dict[str, object] | None = None
    url: str | None = None


class CommitTraceabilityResponse(BaseModel):
    repository: str
    hash: str
    branch: str | None = None
    author: str | None = None
    message: str | None = None
    committed_at: datetime | None = None
    pull_requests: list[PullRequestResponse] = Field(default_factory=list)
    issues: list[IssueResponse] = Field(default_factory=list)


class TraceabilityRepositoryResponse(BaseModel):
    repository: str
    commit_count: int
    pull_request_count: int
    issue_count: int
    commits: list[CommitTraceabilityResponse]


class BuildSummaryResponse(BaseModel):
    id: uuid.UUID
    build_id: str
    product_id: str
    product_name: str
    release: str | None = None
    build_type: BuildType
    status: BuildStatus
    traceability_incomplete: bool
    created_at: datetime
    updated_at: datetime
    released_at: datetime | None = None
    cli_version: str | None = None
    signature: str | None = None
    artifact_count: int = 0
    commit_count: int = 0
    pull_request_count: int = 0
    issue_count: int = 0
    notification_count: int = 0


class BuildDetailResponse(BuildSummaryResponse):
    ci_metadata: dict[str, object] | None = None


class BuildListResponse(BaseModel):
    items: list[BuildSummaryResponse]
    total: int


class BuildArtifactsResponse(BaseModel):
    build_id: str
    product_id: str
    artifacts: list[ArtifactResponse]


class BuildTraceabilityResponse(BaseModel):
    build_id: str
    product_id: str
    status: BuildStatus
    traceability_incomplete: bool
    commit_count: int
    pull_request_count: int
    issue_count: int
    repositories: list[TraceabilityRepositoryResponse]


class BuildComparisonResponse(BaseModel):
    start_build_id: str
    end_build_id: str
    unique_commits: list[str]
    unique_pull_requests: list[PullRequestResponse]
    unique_issues: list[IssueResponse]


class BuildStatusTransitionRequest(BaseModel):
    status: BuildStatus
    comment: str | None = Field(default=None, max_length=2000)


class BuildVerificationArtifactResponse(BaseModel):
    name: str
    type: ArtifactType
    sha256: str
    integrity_status: str
    detail: str


class BuildVerificationResponse(BaseModel):
    build_id: str
    product_id: str
    integrity_status: str
    traceability_incomplete: bool
    artifacts: list[BuildVerificationArtifactResponse]
    verification_timestamp: datetime


class BuildSearchResponse(BaseModel):
    query: str
    items: list[BuildSummaryResponse]
    total: int


class SubscriptionCreateRequest(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=255)
    release: str | None = Field(default=None, min_length=1, max_length=100)
    channel: NotificationChannel
    webhook_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_channel_fields(self) -> SubscriptionCreateRequest:
        if self.channel == NotificationChannel.WEBHOOK and not self.webhook_url:
            msg = "webhook_url is required when channel is webhook."
            raise ValueError(msg)
        return self


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    product_id: str
    product_name: str
    release: str | None = None
    channel: NotificationChannel
    webhook_url: str | None = None
    active: bool
    created_at: datetime


class SubscriptionListResponse(BaseModel):
    items: list[SubscriptionResponse]
    total: int


class ActivityTotalsResponse(BaseModel):
    products: int
    releases: int
    builds: int
    released_builds: int
    incomplete_builds: int


class ActivityResponse(BaseModel):
    generated_at: datetime
    totals: ActivityTotalsResponse
    recent_builds: list[BuildSummaryResponse]
    products: list[ProductSummaryResponse]
