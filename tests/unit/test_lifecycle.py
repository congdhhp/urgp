"""Unit tests for the build lifecycle state machine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from urgp.models.enums import ArtifactType, BuildStatus, BuildType
from urgp.models.manifest import Artifact, BuildManifest
from urgp.services.lifecycle import (
    BuildLifecycleService,
    ImmutableManifestError,
    InvalidBuildTransitionError,
    SignatureVerificationError,
)


def _manifest(status: BuildStatus, *, signature: str | None = None) -> BuildManifest:
    return BuildManifest(
        id=uuid.uuid4(),
        build_id="260330",
        product_id=uuid.uuid4(),
        release_id=uuid.uuid4(),
        build_type=BuildType.NIGHTLY,
        status=status,
        traceability_incomplete=False,
        signature=signature,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


class TestBuildLifecycleService:
    def test_allows_happy_path_release_flow(self) -> None:
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.COMPLETED)

        service.transition(manifest, BuildStatus.TESTING, allow_noop=False)
        transition = service.transition(manifest, BuildStatus.RELEASED, allow_noop=False)

        assert transition.previous_status == BuildStatus.TESTING
        assert transition.new_status == BuildStatus.RELEASED
        assert manifest.released_at is not None

    def test_rejects_invalid_transition(self) -> None:
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.INGESTING)

        with pytest.raises(InvalidBuildTransitionError):
            service.transition(manifest, BuildStatus.RELEASED, allow_noop=False)

    def test_released_manifest_is_immutable_except_for_deprecation(self) -> None:
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.RELEASED)

        with pytest.raises(ImmutableManifestError):
            service.transition(manifest, BuildStatus.TESTING, allow_noop=False)

        service.transition(manifest, BuildStatus.DEPRECATED, allow_noop=False)
        assert manifest.status == BuildStatus.DEPRECATED


class TestSignatureVerificationOnRelease:
    """P1-4.9: HMAC signature re-verification before release transition."""

    def test_unsigned_manifest_cannot_be_released_with_verification(self) -> None:
        """Unsigned manifests are rejected when verification is enabled."""
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.TESTING, signature=None)

        with pytest.raises(SignatureVerificationError, match="no signature"):
            service.transition(
                manifest,
                BuildStatus.RELEASED,
                verify_signature=True,
                signing_key="test-secret",
            )

    def test_release_without_verification_skips_check(self) -> None:
        """Release without verify_signature=True skips signature check."""
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.TESTING, signature=None)

        transition = service.transition(manifest, BuildStatus.RELEASED)
        assert transition.changed is True
        assert manifest.status == BuildStatus.RELEASED

    def test_release_with_signing_key_generates_artifact_signature(self) -> None:
        """Released manifests are signed from build_id + sorted artifact checksums."""
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.TESTING, signature=None)
        manifest.artifacts = [
            Artifact(name="b.zip", type=ArtifactType.GENERIC, storage_uri="file:///b.zip", sha256_checksum="b" * 64),
            Artifact(name="a.zip", type=ArtifactType.GENERIC, storage_uri="file:///a.zip", sha256_checksum="a" * 64),
        ]

        service.transition(manifest, BuildStatus.RELEASED, signing_key="test-secret")

        assert manifest.signature == service.compute_manifest_signature(manifest, "test-secret")

    def test_tampered_signature_is_rejected(self) -> None:
        """Manifest with wrong signature is rejected on release."""
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.TESTING, signature="tampered_signature_hex")

        with pytest.raises(SignatureVerificationError, match="verification failed"):
            service.transition(
                manifest,
                BuildStatus.RELEASED,
                verify_signature=True,
                signing_key="test-secret",
            )

    def test_no_signing_key_skips_verification_gracefully(self) -> None:
        """Missing signing key logs warning but does not block release."""
        service = BuildLifecycleService()
        manifest = _manifest(BuildStatus.TESTING, signature="some_signature")

        transition = service.transition(
            manifest,
            BuildStatus.RELEASED,
            verify_signature=True,
            signing_key=None,  # Not configured
        )
        assert transition.changed is True
        assert manifest.status == BuildStatus.RELEASED
