"""Build lifecycle state machine and immutability rules."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from urgp.models.enums import BuildStatus
from urgp.models.manifest import BuildManifest

logger = logging.getLogger(__name__)


class InvalidBuildTransitionError(ValueError):
    """Raised when a build status transition violates the lifecycle rules."""


class ImmutableManifestError(RuntimeError):
    """Raised when a released manifest would be modified."""


class SignatureVerificationError(RuntimeError):
    """Raised when manifest signature verification fails on release."""


_ALLOWED_TRANSITIONS: dict[BuildStatus, set[BuildStatus]] = {
    BuildStatus.INGESTING: {BuildStatus.HYDRATING},
    BuildStatus.HYDRATING: {BuildStatus.COMPLETED},
    BuildStatus.COMPLETED: {BuildStatus.TESTING, BuildStatus.DEPRECATED},
    BuildStatus.TESTING: {BuildStatus.RELEASED},
    BuildStatus.RELEASED: {BuildStatus.DEPRECATED},
    BuildStatus.DEPRECATED: set(),
}


@dataclass(frozen=True)
class LifecycleTransition:
    """Materialized lifecycle transition outcome."""

    previous_status: BuildStatus
    new_status: BuildStatus
    changed: bool


class BuildLifecycleService:
    """Apply lifecycle state transitions consistently across the platform.

    When transitioning to RELEASED, the service optionally verifies
    the HMAC-SHA256 signature to ensure manifest integrity.
    """

    def transition(
        self,
        manifest: BuildManifest,
        target_status: BuildStatus,
        *,
        allow_noop: bool = True,
        verify_signature: bool = False,
        signing_key: str | None = None,
    ) -> LifecycleTransition:
        """Execute a lifecycle state transition.

        Args:
            manifest: The build manifest to transition.
            target_status: The target lifecycle status.
            allow_noop: If True, same-status transitions are allowed (no-op).
            verify_signature: If True and target is RELEASED, verify HMAC signature.
            signing_key: Required when verify_signature is True.

        Raises:
            ImmutableManifestError: If the manifest is released and target is not DEPRECATED.
            InvalidBuildTransitionError: If the transition is not allowed.
            SignatureVerificationError: If signature verification fails on release.
        """
        current_status = manifest.status

        if current_status == BuildStatus.RELEASED and target_status != BuildStatus.DEPRECATED:
            msg = f"Manifest '{manifest.build_id}' is released and immutable."
            raise ImmutableManifestError(msg)

        if current_status == target_status:
            if allow_noop:
                return LifecycleTransition(
                    previous_status=current_status,
                    new_status=target_status,
                    changed=False,
                )
            msg = f"Manifest '{manifest.build_id}' is already in status '{target_status.value}'."
            raise InvalidBuildTransitionError(msg)

        allowed_targets = _ALLOWED_TRANSITIONS[current_status]
        if target_status not in allowed_targets:
            allowed = (
                ", ".join(status.value for status in sorted(allowed_targets, key=lambda item: item.value)) or "none"
            )
            msg = (
                f"Invalid build lifecycle transition '{current_status.value}' -> '{target_status.value}'. "
                f"Allowed targets: {allowed}."
            )
            raise InvalidBuildTransitionError(msg)

        if target_status == BuildStatus.RELEASED and verify_signature:
            self._verify_manifest_integrity(manifest, signing_key)

        manifest.status = target_status
        if target_status == BuildStatus.RELEASED:
            if signing_key is not None:
                manifest.signature = self.compute_manifest_signature(manifest, signing_key)
            manifest.released_at = datetime.now(tz=UTC)

        return LifecycleTransition(
            previous_status=current_status,
            new_status=target_status,
            changed=True,
        )

    def compute_manifest_signature(self, manifest: BuildManifest, signing_key: str) -> str:
        """Compute the release-lock HMAC over build id and artifact checksums."""
        canonical = _build_canonical_manifest_data(manifest)
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(signing_key.encode("utf-8"), encoded, hashlib.sha256).hexdigest()

    def _verify_manifest_integrity(self, manifest: BuildManifest, signing_key: str | None) -> None:
        """Verify HMAC-SHA256 signature integrity before release.

        Ensures the manifest has not been tampered with since ingestion.
        """
        if not manifest.signature:
            msg = f"Manifest '{manifest.build_id}' has no signature — cannot release unsigned manifests."
            raise SignatureVerificationError(msg)

        if signing_key is None:
            logger.warning(
                "Signature verification requested but no signing key provided for manifest '%s'; skipping",
                manifest.build_id,
            )
            return

        expected = self.compute_manifest_signature(manifest, signing_key)

        if not hmac.compare_digest(expected, manifest.signature):
            msg = (
                f"Manifest '{manifest.build_id}' signature verification failed — "
                f"manifest may have been modified since ingestion."
            )
            raise SignatureVerificationError(msg)

        logger.info("Manifest '%s' signature verified successfully", manifest.build_id)


def _build_canonical_manifest_data(manifest: BuildManifest) -> dict[str, object]:
    """Build canonical data for release signatures."""
    return {
        "build_id": manifest.build_id,
        "artifact_checksums": sorted(artifact.sha256_checksum for artifact in manifest.artifacts),
    }


__all__ = [
    "BuildLifecycleService",
    "ImmutableManifestError",
    "InvalidBuildTransitionError",
    "LifecycleTransition",
    "SignatureVerificationError",
]
