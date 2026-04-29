"""Build lifecycle state machine and immutability rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from urgp.models.enums import BuildStatus
from urgp.models.manifest import BuildManifest


class InvalidBuildTransitionError(ValueError):
    """Raised when a build status transition violates the lifecycle rules."""


class ImmutableManifestError(RuntimeError):
    """Raised when a released manifest would be modified."""


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
    """Apply lifecycle state transitions consistently across the platform."""

    def transition(
        self,
        manifest: BuildManifest,
        target_status: BuildStatus,
        *,
        allow_noop: bool = True,
    ) -> LifecycleTransition:
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

        manifest.status = target_status
        if target_status == BuildStatus.RELEASED:
            manifest.released_at = datetime.now(tz=UTC)

        return LifecycleTransition(
            previous_status=current_status,
            new_status=target_status,
            changed=True,
        )


__all__ = [
    "BuildLifecycleService",
    "ImmutableManifestError",
    "InvalidBuildTransitionError",
    "LifecycleTransition",
]
