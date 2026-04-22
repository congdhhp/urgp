"""API key authentication middleware.

Validates the `X-API-Key` header against configured API keys.
For P1 (MVP), keys are stored in environment variables.
Phase 2 will use database-backed key management with bcrypt hashing.

Reference: docs/07-implementation-plan.md § P1-3.1
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI documentation
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> str:
    """FastAPI dependency that validates the API key from the X-API-Key header.

    Args:
        api_key: The API key extracted from the request header.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 if the key is missing or invalid.
    """
    if not api_key:
        logger.warning("API request rejected: missing X-API-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide a valid key in the X-API-Key header.",
        )

    # Import settings lazily to avoid circular imports during startup
    from urgp.config import get_settings

    settings = get_settings()

    if not settings.api_keys:
        # No keys configured — reject all requests (fail-closed)
        logger.error("No API keys configured — all requests rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication is not configured. Contact an administrator.",
        )

    if api_key not in settings.api_keys:
        logger.warning("API request rejected: invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_key


# Type alias for use in route dependencies
APIKeyDep = Annotated[str, Depends(verify_api_key)]
