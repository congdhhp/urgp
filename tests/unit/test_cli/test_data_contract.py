"""P1-2.T4: Test Data Contract JSON schema compliance.

Verifies that the Pydantic data contract models correctly validate
payloads, enforce required fields, and reject invalid values.

Reference:
    - docs/07-implementation-plan.md § P1-2.T4
    - docs/05-technical-design.md § Data Contract Payload
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from urgp_cli.contracts.data_contract import (
    ArtifactPayload,
    ArtifactTypeEnum,
    BuildEventPayload,
    BuildTypeEnum,
    CommitHash,
)


class TestCommitHash:
    """Test CommitHash model validation."""

    def test_valid_commit_hash(self) -> None:
        """Valid 40-char hex hash accepted."""
        ch = CommitHash(repository="github.com/org/repo", hash="a" * 40)
        assert ch.hash == "a" * 40
        assert ch.repository == "github.com/org/repo"

    def test_uppercase_hash_normalized(self) -> None:
        """Uppercase hex hash is normalized to lowercase."""
        ch = CommitHash(repository="repo", hash="A" * 40)
        assert ch.hash == "a" * 40

    def test_invalid_hash_length(self) -> None:
        """Hash shorter than 40 chars is rejected."""
        with pytest.raises(ValidationError, match="40 lowercase hex"):
            CommitHash(repository="repo", hash="abc123")

    def test_invalid_hash_chars(self) -> None:
        """Non-hex characters are rejected."""
        with pytest.raises(ValidationError, match="40 lowercase hex"):
            CommitHash(repository="repo", hash="g" * 40)

    def test_empty_repository_rejected(self) -> None:
        """Empty repository string is rejected."""
        with pytest.raises(ValidationError):
            CommitHash(repository="", hash="a" * 40)

    def test_optional_branch(self) -> None:
        """Branch field is optional."""
        ch = CommitHash(repository="repo", hash="a" * 40, branch="main")
        assert ch.branch == "main"

        ch2 = CommitHash(repository="repo", hash="a" * 40)
        assert ch2.branch is None


class TestArtifactPayload:
    """Test ArtifactPayload model validation."""

    def test_valid_artifact(self) -> None:
        """Valid artifact payload accepted."""
        art = ArtifactPayload(
            name="s32-ide.zip",
            type=ArtifactTypeEnum.ECLIPSE_P2,
            storage_uri="https://artifacts.example.com/s32-ide.zip",
            sha256="a" * 64,
            size_bytes=1024000,
        )
        assert art.name == "s32-ide.zip"
        assert art.type == ArtifactTypeEnum.ECLIPSE_P2

    def test_invalid_sha256(self) -> None:
        """SHA-256 with wrong length is rejected."""
        with pytest.raises(ValidationError, match="64 lowercase hex"):
            ArtifactPayload(
                name="file.zip",
                type=ArtifactTypeEnum.GENERIC,
                storage_uri="file:///tmp/file.zip",
                sha256="abc123",
            )

    def test_invalid_artifact_type(self) -> None:
        """Unknown artifact type is rejected."""
        with pytest.raises(ValidationError):
            ArtifactPayload(
                name="file.zip",
                type="unknown_type",  # type: ignore[arg-type]
                storage_uri="file:///tmp/file.zip",
                sha256="a" * 64,
            )

    def test_negative_size_rejected(self) -> None:
        """Negative size_bytes is rejected."""
        with pytest.raises(ValidationError):
            ArtifactPayload(
                name="file.zip",
                type=ArtifactTypeEnum.GENERIC,
                storage_uri="file:///file.zip",
                sha256="a" * 64,
                size_bytes=-1,
            )

    def test_optional_metadata(self) -> None:
        """Metadata field is optional."""
        art = ArtifactPayload(
            name="file.zip",
            type=ArtifactTypeEnum.GENERIC,
            storage_uri="file:///file.zip",
            sha256="a" * 64,
            metadata={"key": "value"},
        )
        assert art.metadata == {"key": "value"}


class TestBuildEventPayload:
    """Test BuildEventPayload model validation."""

    @pytest.fixture
    def valid_payload_data(self) -> dict[str, object]:
        """Return minimal valid payload data."""
        return {
            "product_id": "s32-design-studio",
            "release": "3.6.8-RFP",
            "build_type": "nightly",
            "build_id": "260330",
            "cli_version": "0.1.0",
            "commit_hashes": [
                {"repository": "bitbucket.org/nxp/s32k3_dev", "hash": "a" * 40},
            ],
            "artifacts": [
                {
                    "name": "s32-ide.zip",
                    "type": "eclipse_p2",
                    "storage_uri": "https://artifacts.example.com/s32-ide.zip",
                    "sha256": "b" * 64,
                    "size_bytes": 1024000,
                },
            ],
            "timestamp": "2026-03-30T10:00:00Z",
        }

    def test_valid_payload_accepted(self, valid_payload_data: dict[str, object]) -> None:
        """Valid payload is accepted and parsed correctly."""
        payload = BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]
        assert payload.product_id == "s32-design-studio"
        assert payload.build_type == BuildTypeEnum.NIGHTLY
        assert len(payload.commit_hashes) == 1
        assert len(payload.artifacts) == 1

    def test_missing_product_id_rejected(self, valid_payload_data: dict[str, object]) -> None:
        """Missing product_id is rejected."""
        del valid_payload_data["product_id"]  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]

    def test_missing_build_id_rejected(self, valid_payload_data: dict[str, object]) -> None:
        """Missing build_id is rejected."""
        del valid_payload_data["build_id"]  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]

    def test_missing_commit_hashes_rejected(self, valid_payload_data: dict[str, object]) -> None:
        """Missing commit_hashes is rejected."""
        del valid_payload_data["commit_hashes"]  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]

    def test_empty_artifacts_rejected(self, valid_payload_data: dict[str, object]) -> None:
        """Empty artifacts list is rejected (min_length=1)."""
        valid_payload_data["artifacts"] = []
        with pytest.raises(ValidationError):
            BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]

    def test_invalid_build_type_rejected(self, valid_payload_data: dict[str, object]) -> None:
        """Invalid build_type is rejected."""
        valid_payload_data["build_type"] = "invalid_type"
        with pytest.raises(ValidationError):
            BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]

    def test_optional_ci_metadata(self, valid_payload_data: dict[str, object]) -> None:
        """CI metadata is optional."""
        payload = BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]
        assert payload.ci_metadata is None

        valid_payload_data["ci_metadata"] = {
            "ci_system": "Jenkins",
            "pipeline_url": "https://jenkins.example.com/job/build/1",
        }
        payload = BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]
        assert payload.ci_metadata is not None
        assert payload.ci_metadata.ci_system == "Jenkins"

    def test_to_json_dict(self, valid_payload_data: dict[str, object]) -> None:
        """to_json_dict() produces a JSON-serializable dictionary."""
        payload = BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]
        json_dict = payload.to_json_dict()

        assert isinstance(json_dict, dict)
        assert json_dict["product_id"] == "s32-design-studio"
        assert json_dict["build_type"] == "nightly"
        assert isinstance(json_dict["commit_hashes"], list)
        assert isinstance(json_dict["artifacts"], list)

    def test_multi_repo_commits(self, valid_payload_data: dict[str, object]) -> None:
        """Multiple commits from different repos are accepted."""
        valid_payload_data["commit_hashes"] = [
            {"repository": "bitbucket.org/nxp/s32k3_dev", "hash": "a" * 40},
            {"repository": "bitbucket.org/nxp/s32k3_drivers", "hash": "b" * 40},
        ]
        payload = BuildEventPayload(**valid_payload_data)  # type: ignore[arg-type]
        assert len(payload.commit_hashes) == 2

    def test_all_build_types(self) -> None:
        """All build type enum values are valid."""
        assert BuildTypeEnum.NIGHTLY.value == "nightly"
        assert BuildTypeEnum.WEEKLY.value == "weekly"
        assert BuildTypeEnum.RC.value == "rc"
        assert BuildTypeEnum.HOTFIX.value == "hotfix"

    def test_all_artifact_types(self) -> None:
        """All artifact type enum values are valid."""
        expected = {"eclipse_p2", "oci_image", "binary", "npm_tarball", "maven_jar", "python_wheel", "generic"}
        actual = {t.value for t in ArtifactTypeEnum}
        assert actual == expected
