"""API response schemas for the Event Gateway.

Defines structured response bodies for all Gateway endpoints.
Used by FastAPI for OpenAPI documentation and response serialization.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestAcceptedResponse(BaseModel):
    """HTTP 202 response for a successfully accepted build event.

    Returned when a new (non-duplicate) payload passes all validation
    and is published to the RabbitMQ processing queues.
    """

    message: str = Field(
        default="Build event accepted for processing",
        description="Human-readable status message",
    )
    build_id: str = Field(
        ...,
        description="The build identifier from the submitted payload",
    )
    ingestion_timestamp: datetime = Field(
        ...,
        description="Server-side timestamp when the event was ingested",
    )


class IngestDuplicateResponse(BaseModel):
    """HTTP 200 response for an idempotent duplicate submission.

    Returned when the same `build_id + product_id` combination has
    already been processed within the 24-hour idempotency window.
    """

    message: str = Field(
        default="Build event already processed (idempotent)",
        description="Human-readable status message indicating duplicate",
    )
    build_id: str = Field(
        ...,
        description="The build identifier from the submitted payload",
    )
    original_ingestion_timestamp: datetime = Field(
        ...,
        description="Timestamp of the original ingestion",
    )


class IngestInProgressResponse(BaseModel):
    """HTTP 202 response for an event already reserved by another in-flight request."""

    message: str = Field(
        default="Build event is already being processed",
        description="Human-readable status message indicating the event is still in progress",
    )
    build_id: str = Field(
        ...,
        description="The build identifier from the submitted payload",
    )
    reservation_timestamp: datetime = Field(
        ...,
        description="Timestamp when the in-flight reservation started",
    )


class ValidationErrorDetail(BaseModel):
    """Structured validation error detail for HTTP 422 responses.

    Provides actionable error information with field-level detail.
    """

    field: str = Field(
        ...,
        description="The field name that failed validation (dot-separated path)",
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
    )
    input_value: object | None = Field(
        default=None,
        description="The invalid value that was provided",
    )


class ValidationErrorResponse(BaseModel):
    """Structured HTTP 422 response for payload validation failures."""

    error: str = Field(
        default="validation_failed",
        description="Error type identifier",
    )
    message: str = Field(
        default="Payload validation failed.",
        description="Human-readable error message",
    )
    details: list[ValidationErrorDetail] = Field(
        ...,
        description="Field-level validation details",
    )


class RateLimitExceededResponse(BaseModel):
    """HTTP 429 response body when rate limit is exceeded.

    The `Retry-After` header is set separately in the response headers.
    """

    error: str = Field(
        default="rate_limit_exceeded",
        description="Error type identifier",
    )
    message: str = Field(
        default="Too many requests. Please retry after the specified period.",
        description="Human-readable error message",
    )
    limit: int = Field(
        ...,
        description="Maximum number of requests allowed in the window",
    )
    remaining: int = Field(
        default=0,
        description="Number of requests remaining in the current window",
    )
    reset_at: int = Field(
        ...,
        description="Unix timestamp when the rate limit window resets",
    )


class DLQCountResponse(BaseModel):
    """Response body for the DLQ monitoring endpoint.

    Provides visibility into messages that failed processing.
    """

    queue: str = Field(
        default="build.events.dlq",
        description="Name of the Dead Letter Queue",
    )
    message_count: int = Field(
        ...,
        ge=0,
        description="Number of messages currently in the DLQ",
    )
    consumer_count: int = Field(
        default=0,
        ge=0,
        description="Number of active consumers on the DLQ",
    )


class ServiceUnavailableResponse(BaseModel):
    """Structured HTTP 503 response for transient dependency failures."""

    error: str = Field(
        default="service_unavailable",
        description="Error type identifier",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
