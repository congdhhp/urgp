"""Product and release management APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from urgp.dependencies import ReadAccessDep, SessionFactoryDep, WriteAccessDep
from urgp.schemas.platform import (
    ProductCreateRequest,
    ProductListResponse,
    ProductSummaryResponse,
    ReleaseCreateRequest,
    ReleaseListResponse,
    ReleaseSummaryResponse,
)
from urgp.services.platform_queries import PlatformQueryService, ProductNotFoundError

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


@router.get("", response_model=ProductListResponse, summary="List onboarded products")
async def list_products(
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
) -> ProductListResponse:
    service = PlatformQueryService(session_factory)
    return await service.list_products()


@router.post("", response_model=ProductSummaryResponse, status_code=status.HTTP_201_CREATED, summary="Create a product")
async def create_product(
    _api_key: WriteAccessDep,
    payload: ProductCreateRequest,
    session_factory: SessionFactoryDep,
) -> ProductSummaryResponse:
    service = PlatformQueryService(session_factory)
    return await service.create_product(payload)


@router.get(
    "/{product_external_id}/releases",
    response_model=ReleaseListResponse,
    summary="List release trains for a product",
)
async def list_releases(
    product_external_id: str,
    _api_key: ReadAccessDep,
    session_factory: SessionFactoryDep,
) -> ReleaseListResponse:
    service = PlatformQueryService(session_factory)
    try:
        return await service.list_releases(product_external_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{product_external_id}/releases",
    response_model=ReleaseSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a release train for a product",
)
async def create_release(
    product_external_id: str,
    _api_key: WriteAccessDep,
    payload: ReleaseCreateRequest,
    session_factory: SessionFactoryDep,
) -> ReleaseSummaryResponse:
    service = PlatformQueryService(session_factory)
    try:
        return await service.create_release(product_external_id, payload)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
