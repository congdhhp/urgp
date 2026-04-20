"""Request ID middleware.

Generates a UUID for each incoming request and binds it to structlog context
so all log entries within a request share the same request_id.

Reference: docs/07-implementation-plan.md § P1-1.6
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to each request.

    The request ID is:
    - Added to the structlog context (appears in all log entries)
    - Set as a response header (X-Request-ID)
    - Available via request.state.request_id
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request with a unique request ID."""
        request_id = str(uuid.uuid4())

        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Make request_id available to route handlers
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
