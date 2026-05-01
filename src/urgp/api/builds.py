"""Build query, lifecycle, and integrity APIs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from urgp.dependencies import ReadAccessDep, SessionFactoryDep, WriteAccessDep
from urgp.models.enums import BuildStatus, NotificationEventType
from urgp.schemas.notifications import NotificationRequest
from urgp.schemas.platform import (
    BuildArtifactsResponse,
    BuildComparisonResponse,
    BuildDetailResponse,
    BuildListResponse,
    BuildSearchResponse,
    BuildStatusTransitionRequest,
    BuildTraceabilityResponse,
    BuildVerificationResponse,
)
from urgp.services.lifecycle import ImmutableManifestError, InvalidBuildTransitionError
from urgp.services.platform_queries import (
    AmbiguousBuildReferenceError,
    BuildNotFoundError,
    BuildStatusTransitionResult,
    PlatformQueryService,
)

router = APIRouter(prefix="/api/v1/builds", tags=["Builds"])
logger = logging.getLogger(__name__)


def _platform_service(session_factory: SessionFactoryDep) -> PlatformQueryService:
    from urgp.config import get_settings

    settings = get_settings()
    signing_key = getattr(settings, "signing_key", None)
    return PlatformQueryService(session_factory, signing_key=signing_key if isinstance(signing_key, str) else None)


@router.get("", response_model=BuildListResponse, summary="List build manifests")
async def list_builds(
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
    product_id: str | None = Query(default=None),
    release: str | None = Query(default=None),
    status_filter: BuildStatus | None = Query(default=None, alias="status"),
    traceability_incomplete: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> BuildListResponse:
    service = _platform_service(session_factory)
    return await service.list_builds(
        product_id=product_id,
        release=release,
        status=status_filter,
        traceability_incomplete=traceability_incomplete,
        limit=limit,
        offset=offset,
    )


@router.get("/compare", response_model=BuildComparisonResponse, summary="Compare two builds")
async def compare_builds(
    start: str,
    end: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
    product_id: str | None = Query(default=None),
) -> BuildComparisonResponse:
    service = _platform_service(session_factory)
    try:
        return await service.compare_builds(start, end, product_id=product_id)
    except (BuildNotFoundError, AmbiguousBuildReferenceError) as exc:
        raise _build_lookup_http_error(exc) from exc


@router.get(
    "/search/by-commit/{commit_hash}",
    response_model=BuildSearchResponse,
    summary="Find builds containing a commit",
)
async def find_builds_by_commit(
    commit_hash: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
) -> BuildSearchResponse:
    service = _platform_service(session_factory)
    return await service.find_builds_by_commit(commit_hash)


@router.get(
    "/search/by-issue/{issue_id}",
    response_model=BuildSearchResponse,
    summary="Find builds containing an issue",
)
async def find_builds_by_issue(
    issue_id: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
) -> BuildSearchResponse:
    service = _platform_service(session_factory)
    return await service.find_builds_by_issue(issue_id)


@router.get("/{build_ref}", response_model=BuildDetailResponse, summary="Get build details")
async def get_build(
    build_ref: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
    product_id: str | None = Query(default=None),
) -> BuildDetailResponse:
    service = _platform_service(session_factory)
    try:
        return await service.get_build(build_ref, product_id=product_id)
    except (BuildNotFoundError, AmbiguousBuildReferenceError) as exc:
        raise _build_lookup_http_error(exc) from exc


@router.get("/{build_ref}/artifacts", response_model=BuildArtifactsResponse, summary="List build artifacts")
async def get_artifacts(
    build_ref: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
    product_id: str | None = Query(default=None),
) -> BuildArtifactsResponse:
    service = _platform_service(session_factory)
    try:
        return await service.get_artifacts(build_ref, product_id=product_id)
    except (BuildNotFoundError, AmbiguousBuildReferenceError) as exc:
        raise _build_lookup_http_error(exc) from exc


@router.get(
    "/{build_ref}/traceability",
    response_model=BuildTraceabilityResponse,
    summary="Get the traceability graph for a build",
)
async def get_traceability(
    build_ref: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
    product_id: str | None = Query(default=None),
) -> BuildTraceabilityResponse:
    service = _platform_service(session_factory)
    try:
        return await service.get_traceability(build_ref, product_id=product_id)
    except (BuildNotFoundError, AmbiguousBuildReferenceError) as exc:
        raise _build_lookup_http_error(exc) from exc


@router.patch(
    "/{build_ref}/status",
    response_model=BuildDetailResponse,
    summary="Transition a build through the lifecycle",
)
async def transition_build_status(
    build_ref: str,
    _api_key: WriteAccessDep,
    payload: BuildStatusTransitionRequest,
    session_factory: SessionFactoryDep,
    request: Request,
    product_id: str | None = Query(default=None),
) -> BuildDetailResponse:
    service = _platform_service(session_factory)
    try:
        result = await service.transition_build_status(build_ref, payload, product_id=product_id)
    except (BuildNotFoundError, AmbiguousBuildReferenceError) as exc:
        raise _build_lookup_http_error(exc) from exc
    except (InvalidBuildTransitionError, ImmutableManifestError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await _publish_release_notification_if_needed(request, result)
    return result.build


@router.post("/{build_ref}/verify", response_model=BuildVerificationResponse, summary="Verify build integrity")
async def verify_build(
    build_ref: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
    product_id: str | None = Query(default=None),
) -> BuildVerificationResponse:
    service = _platform_service(session_factory)
    try:
        return await service.verify_build_integrity(build_ref, product_id=product_id)
    except (BuildNotFoundError, AmbiguousBuildReferenceError) as exc:
        raise _build_lookup_http_error(exc) from exc


def _build_lookup_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AmbiguousBuildReferenceError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def _publish_release_notification_if_needed(request: Request, result: BuildStatusTransitionResult) -> None:
    """Publish a notification request when a build reaches RELEASED status.

    **Design note — Intentional fire-and-forget (P1 trade-off):**
    This function is called *after* the status transition has been committed.
    If the publish fails (broker unavailable, network error, etc.), the build
    status transition still succeeds and is returned to the caller, but no
    notification event is emitted.  This means a released build could
    silently miss its notification under rare failure conditions.

    This is acceptable for P1 because:
    - The status transition is the primary operation; notification is secondary.
    - The failure is logged at ERROR level for operational visibility.
    - A future P2 improvement should introduce a transactional outbox pattern
      or a compensating background job to guarantee notification delivery.
    """
    if result.status != BuildStatus.RELEASED:
        return

    publisher = getattr(request.app.state, "publisher", None)
    if publisher is None or not getattr(publisher, "is_connected", False):
        logger.warning(
            "Release notification request could not be published because the event publisher is unavailable "
            "[manifest=%s, product=%s]",
            result.manifest_id,
            result.product_id,
        )
        return

    try:
        await publisher.publish_notification_request(
            NotificationRequest(
                manifest_id=result.manifest_id,
                build_id=result.build.build_id,
                product_id=result.product_id,
                event_type=NotificationEventType.BUILD_RELEASED,
                triggered_at=result.build.updated_at,
                trigger_source="build_status_api",
            )
        )
    except Exception:
        logger.exception(
            "Failed to publish release notification request [manifest=%s, product=%s]",
            result.manifest_id,
            result.product_id,
        )
