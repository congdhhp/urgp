"""Response header propagation middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class ResponseHeadersMiddleware(BaseHTTPMiddleware):
    """Attach response headers accumulated in request.state to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        rate_limit_headers = getattr(request.state, "rate_limit_headers", None)
        if isinstance(rate_limit_headers, dict):
            for name, value in rate_limit_headers.items():
                response.headers.setdefault(name, value)

        return response
