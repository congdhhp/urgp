"""Unit tests for the build lifecycle state machine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from urgp.models.enums import BuildStatus, BuildType
from urgp.models.manifest import BuildManifest
from urgp.services.lifecycle import BuildLifecycleService, ImmutableManifestError, InvalidBuildTransitionError


def _manifest(status: BuildStatus) -> BuildManifest:
    return BuildManifest(
        id=uuid.uuid4(),
        build_id="260330",
        product_id=uuid.uuid4(),
        release_id=uuid.uuid4(),
        build_type=BuildType.NIGHTLY,
        status=status,
        traceability_incomplete=False,
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
