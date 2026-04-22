"""Ingestion API — POST /api/v1/ingest.

The primary endpoint of the Event Gateway. Receives build event payloads
from the URGP CLI, validates them, checks for duplicates, and publishes
to RabbitMQ queues for downstream processing.

Pipeline:
    1. API key authentication
    2. Rate limiting (write)
    3. Pydantic schema validation (automatic)
    4. Idempotency check (Redis)
    5. Publish to RabbitMQ (build.process + build.notify)
    6. Return HTTP 202 Accepted

Reference:
    - docs/05-technical-design.md § Layer 2: Event Gateway
    - docs/07-implementation-plan.md § P1-3.1 through P1-3.4
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status

from urgp.dependencies import IdempotencyDep, PublisherDep, RateLimiterDep
from urgp.middleware.api_key_auth import APIKeyDep
from urgp.schemas.ingest import IngestPayload
from urgp.schemas.responses import (
    IngestAcceptedResponse,
    IngestDuplicateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Event Gateway"])


@router.post(
    "/ingest",
    response_model=IngestAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {
            "model": IngestDuplicateResponse,
            "description": "Duplicate build event (idempotent success)",
        },
        401: {"description": "Missing or invalid API key"},
        422: {"description": "Payload validation error"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
    summary="Ingest a build event",
    description=(
        "Accepts a Data Contract JSON payload from the URGP CLI. "
        "Validates, deduplicates, and publishes to processing queues."
    ),
)
async def ingest_build_event(
    payload: IngestPayload,
    api_key: APIKeyDep,
    idempotency: IdempotencyDep,
    publisher: PublisherDep,
    rate_limiter: RateLimiterDep,
    response: Response,
) -> IngestAcceptedResponse | IngestDuplicateResponse:
    """Ingest a build event payload from the URGP CLI.

    This endpoint orchestrates the full ingestion pipeline:
    1. API key is validated (via dependency)
    2. Rate limit is checked (write operation)
    3. Payload is validated against the Data Contract (automatic by FastAPI)
    4. Idempotency is checked in Redis
    5. Payload is published to RabbitMQ
    6. HTTP 202 is returned

    Args:
        payload: Validated ingestion payload.
        api_key: Validated API key (from dependency).
        idempotency: Idempotency service (from dependency).
        publisher: Event publisher (from dependency).
        rate_limiter: Rate limiter (from dependency).
        response: FastAPI response for setting headers.

    Returns:
        IngestAcceptedResponse for new events,
        IngestDuplicateResponse for duplicate events.
    """
    # ── Step 1: Rate Limiting ──────────────────────────────
    from urgp.config import get_settings

    settings = get_settings()
    rate_result = await rate_limiter.check_rate_limit(
        api_key,
        is_write=True,
        read_limit=settings.rate_limit_read,
        write_limit=settings.rate_limit_write,
    )

    # Always set rate limit headers
    response.headers["X-RateLimit-Limit"] = str(rate_result.limit)
    response.headers["X-RateLimit-Remaining"] = str(rate_result.remaining)
    response.headers["X-RateLimit-Reset"] = str(rate_result.reset)

    if not rate_result.allowed:
        retry_after = max(1, rate_result.reset - int(datetime.now(tz=UTC).timestamp()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please retry after the specified period.",
                "limit": rate_result.limit,
                "remaining": 0,
                "reset_at": rate_result.reset,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # ── Step 2: Idempotency Check ─────────────────────────
    idem_result = await idempotency.check_and_mark(
        build_id=payload.build_id,
        product_id=payload.product_id,
    )

    if idem_result.is_duplicate:
        response.status_code = status.HTTP_200_OK
        return IngestDuplicateResponse(
            build_id=payload.build_id,
            original_ingestion_timestamp=idem_result.original_timestamp or datetime.now(tz=UTC),
        )

    # ── Step 3: Publish to RabbitMQ ───────────────────────
    try:
        ingestion_timestamp = await publisher.publish(payload)
    except Exception as e:
        logger.error(
            "Failed to publish build event [build=%s, product=%s]: %s",
            payload.build_id,
            payload.product_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "publish_failed",
                "message": "Failed to publish build event to processing queue. Please retry.",
            },
        ) from e

    logger.info(
        "Build event ingested [build=%s, product=%s, type=%s]",
        payload.build_id,
        payload.product_id,
        payload.build_type.value,
    )

    return IngestAcceptedResponse(
        build_id=payload.build_id,
        ingestion_timestamp=ingestion_timestamp,
    )
