"""Notification subscription management APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from urgp.config import get_settings
from urgp.dependencies import ReadAccessDep, SessionFactoryDep, UserIdDep, WriteAccessDep
from urgp.schemas.platform import SubscriptionCreateRequest, SubscriptionListResponse, SubscriptionResponse
from urgp.services.notification_processing import NotificationProcessingService, SubscriptionNotFoundError

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("/subscriptions", response_model=SubscriptionListResponse, summary="List notification subscriptions")
async def list_subscriptions(
    _api_key: ReadAccessDep,
    user_id: UserIdDep,
    session_factory: SessionFactoryDep,
) -> SubscriptionListResponse:
    service = NotificationProcessingService(lambda: session_factory, get_settings())
    return await service.list_subscriptions(user_id)


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
    service = NotificationProcessingService(lambda: session_factory, get_settings())
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
    service = NotificationProcessingService(lambda: session_factory, get_settings())
    try:
        await service.delete_subscription(user_id, subscription_id)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
