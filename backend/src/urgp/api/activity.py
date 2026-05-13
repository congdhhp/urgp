"""Platform activity and summary APIs."""

from __future__ import annotations

from fastapi import APIRouter

from urgp.dependencies import PlatformServiceDep, ReadAccessDep
from urgp.schemas.platform import ActivityResponse

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


@router.get("", response_model=ActivityResponse, summary="Get platform activity dashboard data")
async def get_activity(
    _api_key: ReadAccessDep,
    platform_service: PlatformServiceDep,
) -> ActivityResponse:
    return await platform_service.get_activity()
