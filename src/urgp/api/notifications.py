"""Notification subscription management APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from urgp.dependencies import ReadAccessDep, SessionFactoryDep, UserIdDep, WriteAccessDep
from urgp.models.enums import NotificationChannel
from urgp.schemas.platform import (
    NotificationHistoryResponse,
    SubscriptionCreateRequest,
    SubscriptionListResponse,
    SubscriptionResponse,
)
from urgp.services.notification_processing import (
    NotificationHistoryService,
    SubscriptionNotFoundError,
    SubscriptionService,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("/subscriptions", response_model=SubscriptionListResponse, summary="List notification subscriptions")
async def list_subscriptions(
    _api_key: ReadAccessDep,
    user_id: UserIdDep,
    session_factory: SessionFactoryDep,
) -> SubscriptionListResponse:
    service = SubscriptionService(lambda: session_factory)
    return await service.list_subscriptions(user_id)


@router.get("/history", response_model=NotificationHistoryResponse, summary="List notification delivery history")
async def list_notification_history(
    _api_key: ReadAccessDep,
    user_id: UserIdDep,
    session_factory: SessionFactoryDep,
    build_id: str | None = Query(default=None),
    product_id: str | None = Query(default=None),
    channel: NotificationChannel | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationHistoryResponse:
    service = NotificationHistoryService(lambda: session_factory)
    try:
        return await service.list_history(
            user_id,
            build_id=build_id,
            product_id=product_id,
            channel=channel,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notification subscription",
)
async def create_subscription(
    _api_key: WriteAccessDep,
    user_id: UserIdDep,
    payload: SubscriptionCreateRequest,
    session_factory: SessionFactoryDep,
) -> SubscriptionResponse:
    service = SubscriptionService(lambda: session_factory)
    try:
        return await service.create_subscription(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/subscriptions/{subscription_id}",
    response_class=Response,
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification subscription",
)
async def delete_subscription(
    subscription_id: uuid.UUID,
    _api_key: WriteAccessDep,
    user_id: UserIdDep,
    session_factory: SessionFactoryDep,
) -> None:
    service = SubscriptionService(lambda: session_factory)
    try:
        await service.delete_subscription(user_id, subscription_id)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
