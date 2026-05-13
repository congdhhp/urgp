"""Ingestion payload schemas — Data Contract validation.

These Pydantic models enforce the Data Contract JSON schema from
docs/05-technical-design.md § Data Contract Payload.

The URGP CLI constructs payloads matching these schemas and POSTs
them to `POST /api/v1/ingest`. FastAPI validates automatically.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from urgp.models.enums import ArtifactType, BuildType


class PullRequestSchema(BaseModel):
    """Optional pull request metadata attached to a commit."""

    external_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="External pull request identifier such as 1234 or PR-1234",
    )
    title: str | None = Field(
        default=None,
        max_length=2000,
        description="Pull request title",
    )
    author: str | None = Field(
        default=None,
        max_length=255,
        description="Pull request author",
    )
    source_branch: str | None = Field(
        default=None,
        max_length=255,
        description="Source branch for the change",
    )
    target_branch: str | None = Field(
        default=None,
        max_length=255,
        description="Target branch for the change",
    )
    merge_timestamp: datetime | None = Field(
        default=None,
        description="When the pull request was merged",
    )
    url: str | None = Field(
        default=None,
        max_length=1000,
        description="Deep link to the pull request",
    )


class CommitHashSchema(BaseModel):
    """A single commit reference within a build.

    Attributes:
        repository: Full repository identifier (e.g., bitbucket.org/org/repo).
        hash: Full 40-character lowercase hex SHA-1 commit hash.
        branch: Optional branch name the commit belongs to.
    """

    repository: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Full repository identifier (e.g., bitbucket.org/org/repo)",
        examples=["bitbucket.org/nxp/s32k3_dev"],
    )
    hash: str = Field(
        ...,
        pattern=r"^[a-f0-9]{40}$",
        description="Full 40-character lowercase hex SHA-1 commit hash",
        examples=["abc123def456789012345678901234567890abcd"],
    )
    branch: str | None = Field(
        default=None,
        max_length=255,
        description="Branch name the commit belongs to",
        examples=["main", "develop"],
    )
    author: str | None = Field(
        default=None,
        max_length=255,
        description="Optional commit author for richer traceability and portal views",
    )
    message: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional commit message used for issue extraction and change summaries",
    )
    committed_at: datetime | None = Field(
        default=None,
        description="Optional commit timestamp from the source control system",
    )
    issue_ids: list[str] | None = Field(
        default=None,
        description="Optional explicit issue identifiers already resolved by the producer",
    )
    pull_request: PullRequestSchema | None = Field(
        default=None,
        description="Optional pull request metadata if the producer already knows it",
    )


class ArtifactSchema(BaseModel):
    """A single build artifact with integrity metadata.

    Attributes:
        name: Human-readable artifact name.
        type: Artifact type classification.
        storage_uri: URI where the artifact is stored.
        sha256: SHA-256 hex digest (64 lowercase hex chars).
        size_bytes: File size in bytes.
        metadata: Technology-specific metadata (e.g., Eclipse P2 features).
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable artifact name",
        examples=["s32-ide.zip"],
    )
    type: ArtifactType = Field(
        ...,
        description="Artifact type classification",
        examples=["eclipse_p2", "generic"],
    )
    storage_uri: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="URI where the artifact is stored",
        examples=["https://artifacts.internal/builds/260330/s32-ide.zip"],
    )
    sha256: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hex digest (64 lowercase hex chars)",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="File size in bytes",
    )
    metadata: dict[str, object] | None = Field(
        default=None,
        description="Technology-specific metadata (e.g., Eclipse P2 features, OCI layers)",
    )


class CIMetadataSchema(BaseModel):
    """Optional CI/CD pipeline metadata attached to a build event.

    Attributes:
        ci_system: Name of the CI system (e.g., Jenkins, GitHub Actions).
        pipeline_url: URL to the CI pipeline run.
        triggered_by: User or event that triggered the build.
    """

    ci_system: str | None = Field(
        default=None,
        max_length=100,
        description="Name of the CI system",
        examples=["Jenkins", "GitHub Actions"],
    )
    pipeline_url: str | None = Field(
        default=None,
        max_length=1000,
        description="URL to the CI pipeline run",
    )
    triggered_by: str | None = Field(
        default=None,
        max_length=200,
        description="User or event that triggered the build",
    )


class IngestPayload(BaseModel):
    """Full ingestion payload — the Data Contract between CLI and Event Gateway.

    This is the primary request body for `POST /api/v1/ingest`. The URGP CLI
    constructs this payload and sends it over HTTPS.

    Reference: docs/05-technical-design.md § Data Contract Payload
    """

    product_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Product identifier",
        examples=["S32_IDE"],
    )
    release: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Release train version",
        examples=["3.6.8-RFP"],
    )
    build_type: BuildType = Field(
        ...,
        description="Build type classification",
        examples=["nightly", "weekly"],
    )
    build_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique build identifier",
        examples=["260330"],
    )
    cli_version: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="CLI and data contract version for compatibility tracking",
        examples=["1.0.0"],
    )
    commit_hashes: list[CommitHashSchema] = Field(
        ...,
        min_length=1,
        description="List of commit references included in this build",
    )
    artifacts: list[ArtifactSchema] = Field(
        ...,
        min_length=1,
        description="List of build output artifacts",
    )
    timestamp: datetime = Field(
        ...,
        description="Build timestamp (ISO 8601)",
    )
    ci_metadata: CIMetadataSchema | None = Field(
        default=None,
        description="Optional CI/CD pipeline metadata",
    )

    # ─────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────

    @field_validator("commit_hashes")
    @classmethod
    def validate_commit_hashes_not_empty(cls, v: list[CommitHashSchema]) -> list[CommitHashSchema]:
        """Ensure at least one commit hash is provided."""
        if not v:
            msg = "At least one commit hash is required"
            raise ValueError(msg)
        return v

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts_not_empty(cls, v: list[ArtifactSchema]) -> list[ArtifactSchema]:
        """Ensure at least one artifact is provided."""
        if not v:
            msg = "At least one artifact is required"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_unique_artifact_checksums(self) -> IngestPayload:
        """Ensure all artifact SHA-256 checksums are unique within the payload."""
        seen: set[str] = set()
        duplicates: set[str] = set()

        for artifact in self.artifacts:
            if artifact.sha256 in seen:
                duplicates.add(artifact.sha256)
            else:
                seen.add(artifact.sha256)

        if duplicates:
            msg = f"Duplicate artifact SHA-256 checksums found: {', '.join(sorted(duplicates))}"
            raise ValueError(msg)
        return self
