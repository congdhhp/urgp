"""Unit tests for deterministic manifest signatures."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from urgp.models.enums import ArtifactType, BuildType
from urgp.schemas.ingest import IngestPayload
from urgp.services.signature import ManifestSignatureService


def _payload() -> IngestPayload:
    return IngestPayload(
        product_id="s32-design-studio",
        release="3.6.8-RFP",
        build_type=BuildType.NIGHTLY,
        build_id="260330",
        cli_version="1.0.0",
        commit_hashes=[
            {
                "repository": "bitbucket.org/nxp/s32k3_drivers",
                "hash": "b" * 40,
                "branch": "develop",
            },
            {
                "repository": "bitbucket.org/nxp/s32k3_dev",
                "hash": "a" * 40,
                "branch": "main",
            },
        ],
        artifacts=[
            {
                "name": "s32-ide-symbols.zip",
                "type": ArtifactType.GENERIC,
                "storage_uri": "https://artifacts.internal/symbols.zip",
                "sha256": "b" * 64,
                "metadata": {"classifier": "symbols"},
            },
            {
                "name": "s32-ide.zip",
                "type": ArtifactType.ECLIPSE_P2,
                "storage_uri": "https://artifacts.internal/s32-ide.zip",
                "sha256": "a" * 64,
            },
        ],
        timestamp=datetime(2026, 4, 23, 9, 15, tzinfo=UTC),
        ci_metadata={
            "ci_system": "Jenkins",
            "pipeline_url": "https://jenkins.example.com/job/260330",
            "triggered_by": "nightly",
        },
    )


class TestManifestSignatureService:
    """Manifest signatures must be deterministic and tamper evident."""

    def test_signature_is_stable_across_list_ordering(self) -> None:
        signer = ManifestSignatureService("test-signing-key-must-be-at-least-32-characters-long")
        original = _payload()

        reordered = deepcopy(original.model_dump(mode="json"))
        reordered["commit_hashes"] = list(reversed(reordered["commit_hashes"]))
        reordered["artifacts"] = list(reversed(reordered["artifacts"]))

        reordered_payload = IngestPayload.model_validate(reordered)

        assert signer.sign_payload(original) == signer.sign_payload(reordered_payload)

    def test_signature_verification_detects_payload_changes(self) -> None:
        signer = ManifestSignatureService("test-signing-key-must-be-at-least-32-characters-long")
        payload = _payload()
        signature = signer.sign_payload(payload)

        mutated = payload.model_copy(update={"build_id": "260331"})

        assert signer.verify_payload(payload, signature) is True
        assert signer.verify_payload(mutated, signature) is False
