"""FastAPI exception handlers for API contract and operational correctness."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from urgp.schemas.responses import ValidationErrorDetail, ValidationErrorResponse

logger = logging.getLogger(__name__)


def _format_validation_error(error: dict[str, Any]) -> ValidationErrorDetail:
    location = [str(part) for part in error.get("loc", ()) if part != "body"]
    field = ".".join(location) if location else "body"
    return ValidationErrorDetail(
        field=field,
        message=str(error.get("msg", "Validation failed")),
        input_value=error.get("input"),
    )


def _truncate_body(raw_body: bytes, max_bytes: int) -> str:
    if len(raw_body) <= max_bytes:
        return raw_body.decode("utf-8", errors="replace")

    truncated = raw_body[:max_bytes].decode("utf-8", errors="replace")
    return f"{truncated}...[truncated {len(raw_body) - max_bytes} bytes]"


async def request_validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a structured 422 response and publish invalid ingest payloads to the DLQ."""
    if not isinstance(exc, RequestValidationError):
        raise TypeError("request_validation_exception_handler expects RequestValidationError")

    details = [_format_validation_error(error) for error in exc.errors()]
    response_body = ValidationErrorResponse(details=details).model_dump(mode="json")

    logger.warning(
        "Payload validation failed [path=%s, request_id=%s, errors=%d]",
        request.url.path,
        getattr(request.state, "request_id", None),
        len(details),
    )

    if request.url.path == "/api/v1/ingest":
        from urgp.config import get_settings

        settings = get_settings()
        raw_body = _truncate_body(await request.body(), settings.validation_dlq_max_body_bytes)
        publisher = getattr(request.app.state, "publisher", None)

        if publisher is not None and publisher.is_connected:
            try:
                await publisher.publish_validation_failure(
                    raw_body=raw_body,
                    validation_errors=[detail.model_dump(mode="json") for detail in details],
                    request_context={
                        "path": request.url.path,
                        "method": request.method,
                        "request_id": getattr(request.state, "request_id", None),
                        "content_type": request.headers.get("content-type"),
                    },
                )
            except Exception:
                logger.exception("Failed to publish validation failure to DLQ")
        else:
            logger.error("Validation failure could not be published to DLQ because RabbitMQ is unavailable")

    return JSONResponse(
        status_code=422,
        content=response_body,
    )
