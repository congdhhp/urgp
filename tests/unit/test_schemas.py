"""Unit tests for ingestion payload schemas (Data Contract validation).

Tests cover:
- Valid payload acceptance
- Required field validation
- Regex pattern validation (SHA-1, SHA-256)
- Enum validation (build_type, artifact_type)
- Custom validators (non-empty lists, unique checksums)
- Nested model validation
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from urgp.schemas.ingest import (
    ArtifactSchema,
    CIMetadataSchema,
    CommitHashSchema,
    IngestPayload,
)

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _valid_commit() -> dict:
    """Return a valid commit hash dict."""
    return {
        "repository": "bitbucket.org/nxp/s32k3_dev",
        "hash": "a" * 40,
        "branch": "main",
    }


def _valid_artifact() -> dict:
    """Return a valid artifact dict."""
    return {
        "name": "s32-ide.zip",
        "type": "eclipse_p2",
        "storage_uri": "https://artifacts.internal/builds/260330/s32-ide.zip",
        "sha256": "a" * 64,
        "size_bytes": 1024000,
    }


def _valid_payload() -> dict:
    """Return a valid full ingestion payload dict."""
    return {
        "product_id": "S32_IDE",
        "release": "3.6.8-RFP",
        "build_type": "nightly",
        "build_id": "260330",
        "cli_version": "1.0.0",
        "commit_hashes": [_valid_commit()],
        "artifacts": [_valid_artifact()],
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


# ─────────────────────────────────────────────
# CommitHashSchema Tests
# ─────────────────────────────────────────────


class TestCommitHashSchema:
    """Tests for CommitHashSchema validation."""

    def test_valid_commit(self) -> None:
        """Valid commit hash is accepted."""
        commit = CommitHashSchema(**_valid_commit())
        assert commit.repository == "bitbucket.org/nxp/s32k3_dev"
        assert commit.hash == "a" * 40
        assert commit.branch == "main"

    def test_commit_without_branch(self) -> None:
        """Branch is optional."""
        data = _valid_commit()
        del data["branch"]
        commit = CommitHashSchema(**data)
        assert commit.branch is None

    def test_invalid_hash_too_short(self) -> None:
        """Hash shorter than 40 chars is rejected."""
        data = _valid_commit()
        data["hash"] = "abc123"
        with pytest.raises(ValidationError, match="String should match pattern"):
            CommitHashSchema(**data)

    def test_invalid_hash_uppercase(self) -> None:
        """Uppercase hex chars in hash are rejected (strict lowercase)."""
        data = _valid_commit()
        data["hash"] = "A" * 40
        with pytest.raises(ValidationError, match="String should match pattern"):
            CommitHashSchema(**data)

    def test_empty_repository(self) -> None:
        """Empty repository string is rejected."""
        data = _valid_commit()
        data["repository"] = ""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            CommitHashSchema(**data)


# ─────────────────────────────────────────────
# ArtifactSchema Tests
# ─────────────────────────────────────────────


class TestArtifactSchema:
    """Tests for ArtifactSchema validation."""

    def test_valid_artifact(self) -> None:
        """Valid artifact is accepted."""
        artifact = ArtifactSchema(**_valid_artifact())
        assert artifact.name == "s32-ide.zip"
        assert artifact.sha256 == "a" * 64

    def test_invalid_sha256_too_short(self) -> None:
        """SHA-256 shorter than 64 chars is rejected."""
        data = _valid_artifact()
        data["sha256"] = "abc123"
        with pytest.raises(ValidationError, match="String should match pattern"):
            ArtifactSchema(**data)

    def test_invalid_artifact_type(self) -> None:
        """Invalid artifact type enum is rejected."""
        data = _valid_artifact()
        data["type"] = "invalid_type"
        with pytest.raises(ValidationError):
            ArtifactSchema(**data)

    def test_artifact_without_optional_fields(self) -> None:
        """Optional fields can be omitted."""
        data = _valid_artifact()
        del data["size_bytes"]
        artifact = ArtifactSchema(**data)
        assert artifact.size_bytes is None

    def test_negative_size_bytes(self) -> None:
        """Negative size_bytes is rejected."""
        data = _valid_artifact()
        data["size_bytes"] = -1
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ArtifactSchema(**data)


# ─────────────────────────────────────────────
# CIMetadataSchema Tests
# ─────────────────────────────────────────────


class TestCIMetadataSchema:
    """Tests for CIMetadataSchema validation."""

    def test_valid_ci_metadata(self) -> None:
        """Valid CI metadata is accepted."""
        meta = CIMetadataSchema(
            ci_system="Jenkins",
            pipeline_url="https://jenkins.internal/job/s32-build/260330",
            triggered_by="timer",
        )
        assert meta.ci_system == "Jenkins"

    def test_empty_ci_metadata(self) -> None:
        """All fields are optional."""
        meta = CIMetadataSchema()
        assert meta.ci_system is None
        assert meta.pipeline_url is None
        assert meta.triggered_by is None


# ─────────────────────────────────────────────
# IngestPayload Tests
# ─────────────────────────────────────────────


class TestIngestPayload:
    """Tests for IngestPayload validation (full Data Contract)."""

    def test_valid_payload(self) -> None:
        """Valid full payload is accepted."""
        payload = IngestPayload(**_valid_payload())
        assert payload.product_id == "S32_IDE"
        assert payload.build_id == "260330"
        assert len(payload.commit_hashes) == 1
        assert len(payload.artifacts) == 1

    def test_valid_payload_with_ci_metadata(self) -> None:
        """Payload with optional CI metadata is accepted."""
        data = _valid_payload()
        data["ci_metadata"] = {
            "ci_system": "Jenkins",
            "pipeline_url": "https://jenkins.internal/job/build/1",
        }
        payload = IngestPayload(**data)
        assert payload.ci_metadata is not None
        assert payload.ci_metadata.ci_system == "Jenkins"

    def test_missing_required_field(self) -> None:
        """Missing required field raises validation error."""
        data = _valid_payload()
        del data["build_id"]
        with pytest.raises(ValidationError, match="build_id"):
            IngestPayload(**data)

    def test_invalid_build_type(self) -> None:
        """Invalid build_type enum value is rejected."""
        data = _valid_payload()
        data["build_type"] = "invalid"
        with pytest.raises(ValidationError):
            IngestPayload(**data)

    def test_empty_commit_hashes(self) -> None:
        """Empty commit_hashes list is rejected."""
        data = _valid_payload()
        data["commit_hashes"] = []
        with pytest.raises(ValidationError, match="too_short"):
            IngestPayload(**data)

    def test_empty_artifacts(self) -> None:
        """Empty artifacts list is rejected."""
        data = _valid_payload()
        data["artifacts"] = []
        with pytest.raises(ValidationError, match="too_short"):
            IngestPayload(**data)

    def test_duplicate_artifact_checksums(self) -> None:
        """Duplicate SHA-256 checksums within artifacts are rejected."""
        data = _valid_payload()
        data["artifacts"] = [_valid_artifact(), _valid_artifact()]
        with pytest.raises(ValidationError, match="Duplicate artifact SHA-256"):
            IngestPayload(**data)

    def test_multiple_unique_artifacts(self) -> None:
        """Multiple artifacts with unique checksums are accepted."""
        data = _valid_payload()
        artifact2 = _valid_artifact()
        artifact2["sha256"] = "b" * 64
        artifact2["name"] = "s32-ide-docs.zip"
        data["artifacts"] = [_valid_artifact(), artifact2]
        payload = IngestPayload(**data)
        assert len(payload.artifacts) == 2

    def test_multiple_commits_from_different_repos(self) -> None:
        """Multiple commits from different repos are accepted."""
        data = _valid_payload()
        commit2 = _valid_commit()
        commit2["repository"] = "bitbucket.org/nxp/s32k3_drivers"
        commit2["hash"] = "b" * 40
        data["commit_hashes"] = [_valid_commit(), commit2]
        payload = IngestPayload(**data)
        assert len(payload.commit_hashes) == 2

    def test_all_build_types(self) -> None:
        """All valid build types are accepted."""
        for build_type in ["nightly", "weekly", "rc", "hotfix"]:
            data = _valid_payload()
            data["build_type"] = build_type
            payload = IngestPayload(**data)
            assert payload.build_type.value == build_type

    def test_cli_v1_minimal_commit_backward_compatible(self) -> None:
        """CLI v1 payloads (only repository, hash, branch) remain valid after schema extensions."""
        data = _valid_payload()
        data["commit_hashes"] = [
            {"repository": "bitbucket.org/nxp/s32k3_dev", "hash": "a" * 40, "branch": "main"},
        ]
        payload = IngestPayload(**data)
        commit = payload.commit_hashes[0]
        assert commit.repository == "bitbucket.org/nxp/s32k3_dev"
        assert commit.hash == "a" * 40
        assert commit.branch == "main"
        assert commit.author is None
        assert commit.message is None
        assert commit.committed_at is None
        assert commit.issue_ids is None
        assert commit.pull_request is None

    def test_extended_commit_with_traceability_fields(self) -> None:
        """Commit payloads with new traceability metadata (author, message, PR, issues) parse correctly."""
        data = _valid_payload()
        data["commit_hashes"] = [
            {
                "repository": "bitbucket.org/nxp/s32k3_dev",
                "hash": "b" * 40,
                "branch": "feature/ABC-123",
                "author": "dev@example.com",
                "message": "fix(core): resolve ABC-123 concurrency issue",
                "committed_at": "2026-04-23T10:00:00Z",
                "issue_ids": ["ABC-123", "ABC-456"],
                "pull_request": {
                    "external_id": "PR-789",
                    "title": "Fix concurrency issue",
                    "author": "dev@example.com",
                    "source_branch": "feature/ABC-123",
                    "target_branch": "main",
                    "url": "https://bitbucket.org/nxp/s32k3_dev/pull-requests/789",
                },
            },
        ]
        payload = IngestPayload(**data)
        commit = payload.commit_hashes[0]
        assert commit.author == "dev@example.com"
        assert commit.message == "fix(core): resolve ABC-123 concurrency issue"
        assert commit.issue_ids == ["ABC-123", "ABC-456"]
        assert commit.pull_request is not None
        assert commit.pull_request.external_id == "PR-789"
        assert commit.pull_request.title == "Fix concurrency issue"
        assert commit.pull_request.source_branch == "feature/ABC-123"
        assert commit.pull_request.target_branch == "main"
