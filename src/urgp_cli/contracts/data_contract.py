"""Data Contract models — Pydantic v2 schemas for URGP build event payloads.

Defines the standardized JSON payload structure that the CLI constructs
and transmits to the Event Gateway. The schema matches the Data Contract
specification in the technical design document.

Reference:
    - docs/05-technical-design.md § Data Contract Payload
    - docs/07-implementation-plan.md § P1-2.4
    - Requirement R3.4, R4.4
"""

from __future__ import annotations

import datetime
import re
from enum import Enum
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BuildTypeEnum(str, Enum):
    """Build type classification matching the database enum."""

    NIGHTLY = "nightly"
    WEEKLY = "weekly"
    RC = "rc"
    HOTFIX = "hotfix"


class ArtifactTypeEnum(str, Enum):
    """Artifact type classification matching the database enum."""

    ECLIPSE_P2 = "eclipse_p2"
    OCI_IMAGE = "oci_image"
    BINARY = "binary"
    NPM_TARBALL = "npm_tarball"
    MAVEN_JAR = "maven_jar"
    PYTHON_WHEEL = "python_wheel"
    GENERIC = "generic"


_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_COMMIT_HASH_PATTERN = re.compile(r"^[a-f0-9]{40}$")


def _validate_absolute_uri(value: str, *, field_name: str) -> str:
    """Validate that a field contains an absolute URI."""
    normalized = value.strip()
    parsed = urlsplit(normalized)

    if not normalized:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)

    if not parsed.scheme:
        msg = f"{field_name} must be an absolute URI with a scheme"
        raise ValueError(msg)

    if parsed.scheme == "file":
        if not parsed.path:
            msg = f"{field_name} must include an absolute file path"
            raise ValueError(msg)
        return normalized

    if not parsed.netloc and not parsed.path:
        msg = f"{field_name} must include a network location or path"
        raise ValueError(msg)

    return normalized


class CommitHash(BaseModel):
    """A commit hash entry linking a repository to a specific commit.

    Supports multi-repo builds where commits come from different repositories.
    """

    model_config = ConfigDict(frozen=True)

    repository: str = Field(
        ...,
        min_length=1,
        description="Full repository identifier (e.g., 'bitbucket.org/org/repo')",
    )
    hash: str = Field(
        ...,
        description="Full 40-character lowercase hex SHA-1 commit hash",
    )
    branch: str | None = Field(
        default=None,
        description="Branch name (optional)",
    )

    @field_validator("hash")
    @classmethod
    def validate_commit_hash(cls, v: str) -> str:
        """Validate that the commit hash is a 40-character hex string."""
        normalized = v.lower().strip()
        if not _COMMIT_HASH_PATTERN.match(normalized):
            msg = f"Commit hash must be 40 lowercase hex characters, got: '{v}'"
            raise ValueError(msg)
        return normalized


class ArtifactPayload(BaseModel):
    """An artifact entry in the build event payload."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        ...,
        min_length=1,
        description="Artifact file name",
    )
    type: ArtifactTypeEnum = Field(
        ...,
        description="Artifact type classification",
    )
    storage_uri: str = Field(
        ...,
        min_length=1,
        description="URI to the artifact in external storage (S3, Nexus, SharePoint, etc.)",
    )
    sha256: str = Field(
        ...,
        description="SHA-256 checksum of the artifact (64-character lowercase hex)",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="File size in bytes",
    )
    metadata: dict[str, object] | None = Field(
        default=None,
        description="Technology-specific metadata extracted by the adapter",
    )

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        """Validate that SHA-256 is a 64-character hex string."""
        normalized = v.lower().strip()
        if not _SHA256_PATTERN.match(normalized):
            msg = f"SHA-256 must be 64 lowercase hex characters, got: '{v}'"
            raise ValueError(msg)
        return normalized

    @field_validator("storage_uri")
    @classmethod
    def validate_storage_uri(cls, v: str) -> str:
        """Validate that storage_uri is a well-formed absolute URI."""
        return _validate_absolute_uri(v, field_name="storage_uri")


class CIMetadata(BaseModel):
    """Optional CI/CD pipeline metadata attached to the build event."""

    model_config = ConfigDict(frozen=True)

    ci_system: str | None = Field(default=None, description="CI system name (e.g., 'Jenkins', 'GitHub Actions')")
    pipeline_url: str | None = Field(default=None, description="URL to the CI/CD pipeline run")
    triggered_by: str | None = Field(default=None, description="User or trigger that initiated the build")

    @field_validator("pipeline_url")
    @classmethod
    def validate_pipeline_url(cls, v: str | None) -> str | None:
        """Validate pipeline_url when provided."""
        if v is None:
            return None
        return _validate_absolute_uri(v, field_name="pipeline_url")


class BuildEventPayload(BaseModel):
    """Top-level Data Contract payload for build event ingestion.

    This is the primary payload transmitted by ``urgp-cli push`` to the
    Event Gateway at ``POST /api/v1/ingest``.
    """

    model_config = ConfigDict(frozen=True)

    product_id: str = Field(
        ...,
        min_length=1,
        description="Product identifier",
    )
    release: str = Field(
        ...,
        min_length=1,
        description="Release train version (e.g., '3.6.8-RFP')",
    )
    build_type: BuildTypeEnum = Field(
        ...,
        description="Build cadence classification",
    )
    build_id: str = Field(
        ...,
        min_length=1,
        description="Unique build identifier within the product",
    )
    cli_version: str = Field(
        ...,
        min_length=1,
        description="CLI version and data contract version for compatibility tracking",
    )
    commit_hashes: list[CommitHash] = Field(
        ...,
        min_length=1,
        description="List of commits included in this build (supports multi-repo builds)",
    )
    artifacts: list[ArtifactPayload] = Field(
        ...,
        min_length=1,
        description="List of artifacts produced by the build",
    )
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC),
        description="Build event timestamp (ISO 8601)",
    )
    ci_metadata: CIMetadata | None = Field(
        default=None,
        description="Optional CI/CD pipeline metadata",
    )

    def to_json_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            Dict ready for JSON serialization with ISO timestamps and enum values.
        """
        return self.model_dump(mode="json")
