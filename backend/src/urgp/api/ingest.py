"""Ingestion API — POST /api/v1/ingest."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from urgp.dependencies import IdempotencyDep, PublisherDep, WriteAccessDep, _service_unavailable
from urgp.schemas.ingest import IngestPayload
from urgp.schemas.responses import (
    IngestAcceptedResponse,
    IngestDuplicateResponse,
    IngestInProgressResponse,
    RateLimitExceededResponse,
    ServiceUnavailableResponse,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Event Gateway"])


@router.post(
    "/ingest",
    response_model=IngestAcceptedResponse | IngestDuplicateResponse | IngestInProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {
            "model": IngestDuplicateResponse,
            "description": "Duplicate build event (idempotent success)",
        },
        202: {
            "model": IngestInProgressResponse,
            "description": "Build event is already being processed by another in-flight request",
        },
        401: {"description": "Missing or invalid API key"},
        422: {
            "model": ValidationErrorResponse,
            "description": "Payload validation error",
        },
        429: {
            "model": RateLimitExceededResponse,
            "description": "Rate limit exceeded",
        },
        503: {
            "model": ServiceUnavailableResponse,
            "description": "Transient dependency failure",
        },
    },
    summary="Ingest a build event",
    description=(
        "Accepts a Data Contract JSON payload from the URGP CLI. "
        "Validates, deduplicates, and publishes to processing queues."
    ),
)
async def ingest_build_event(
    api_key: WriteAccessDep,
    payload: IngestPayload,
    idempotency: IdempotencyDep,
    publisher: PublisherDep,
    response: Response,
) -> IngestAcceptedResponse | IngestDuplicateResponse | IngestInProgressResponse:
    """Ingest a build event payload from the URGP CLI."""
    reservation = await idempotency.begin_processing(
        build_id=payload.build_id,
        product_id=payload.product_id,
    )

    if reservation.status == "duplicate":
        response.status_code = status.HTTP_200_OK
        return IngestDuplicateResponse(
            build_id=payload.build_id,
            original_ingestion_timestamp=reservation.original_timestamp or payload.timestamp,
        )

    if reservation.status == "in_progress":
        response.status_code = status.HTTP_202_ACCEPTED
        return IngestInProgressResponse(
            build_id=payload.build_id,
            reservation_timestamp=reservation.pending_since or payload.timestamp,
        )

    try:
        ingestion_timestamp = await publisher.publish(payload)
    except Exception as exc:
        logger.error(
            "Failed to publish build event [build=%s, product=%s]: %s",
            payload.build_id,
            payload.product_id,
            exc,
        )
        try:
            if reservation.reservation_token is not None:
                await idempotency.release_reservation(
                    build_id=payload.build_id,
                    product_id=payload.product_id,
                    reservation_token=reservation.reservation_token,
                )
        except Exception:
            logger.exception(
                "Failed to release idempotency reservation after publish failure [build=%s, product=%s]",
                payload.build_id,
                payload.product_id,
            )

        raise _service_unavailable(
            "RabbitMQ is unavailable. Please retry the ingestion request.",
            error="broker_unavailable",
        ) from exc

    if reservation.reservation_token is not None:
        try:
            finalized = await idempotency.mark_completed(
                build_id=payload.build_id,
                product_id=payload.product_id,
                reservation_token=reservation.reservation_token,
                ingestion_timestamp=ingestion_timestamp,
            )
            if not finalized:
                logger.error(
                    "Published build event but failed to finalize idempotency state [build=%s, product=%s]",
                    payload.build_id,
                    payload.product_id,
                )
        except Exception:
            logger.exception(
                "Published build event but idempotency completion failed [build=%s, product=%s]",
                payload.build_id,
                payload.product_id,
            )

    logger.info(
        "Build event ingested [build=%s, product=%s, type=%s, api_key=%s]",
        payload.build_id,
        payload.product_id,
        payload.build_type.value,
        "authenticated" if api_key else "unknown",
    )

    return IngestAcceptedResponse(
        build_id=payload.build_id,
        ingestion_timestamp=ingestion_timestamp,
    )
