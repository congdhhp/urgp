"""Platform activity and summary APIs."""

from __future__ import annotations

from fastapi import APIRouter

from urgp.dependencies import ReadAccessDep, SessionFactoryDep
from urgp.schemas.platform import ActivityResponse
from urgp.services.platform_queries import PlatformQueryService

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


@router.get("", response_model=ActivityResponse, summary="Get platform activity dashboard data")
async def get_activity(
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
) -> ActivityResponse:
    service = PlatformQueryService(session_factory)
    return await service.get_activity()
