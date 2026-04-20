"""HTTPS transport client with retry logic and fallback support.

Transmits Data Contract payloads to the URGP Event Gateway with:
    - Exponential backoff retry (3 attempts: 1s → 2s → 4s)
    - Timeout per attempt (30 seconds)
    - Local fallback file if all retries are exhausted
    - Clear error reporting for debugging

Reference:
    - docs/05-technical-design.md § Layer 1: Execution Edge
    - docs/07-implementation-plan.md § P1-2.5
    - Requirements: R3.6, R3.7, R3.8, R3.9, R3.11
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from urgp_cli.contracts.data_contract import BuildEventPayload

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 1.0
_REQUEST_TIMEOUT_SECONDS = 30.0

# HTTP status codes that warrant a retry (server-side / transient errors)
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


@dataclass(frozen=True)
class PushResult:
    """Result of a push operation.

    Attributes:
        success: Whether the payload was accepted by the server.
        status_code: HTTP status code from the server (None if no response).
        message: Human-readable result description.
        fallback_path: Path to the fallback JSON file (None if not needed).
    """

    success: bool
    status_code: int | None
    message: str
    fallback_path: str | None = None


class URGPClient:
    """HTTP client for transmitting build event payloads to the URGP API.

    Handles authentication, retries, timeouts, and local fallback files.

    Args:
        api_url: Base URL of the URGP API (e.g., ``https://urgp.internal``).
        timeout: Request timeout in seconds per attempt.
        max_retries: Maximum number of retry attempts.
    """

    def __init__(
        self,
        api_url: str,
        *,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def ingest_url(self) -> str:
        """Full URL for the ingestion endpoint."""
        return f"{self._api_url}/api/v1/ingest"

    def push(self, payload: BuildEventPayload, api_key: str) -> PushResult:
        """Transmit a build event payload to the URGP Event Gateway.

        Implements exponential backoff retry on transient failures:
            - Attempt 1: immediate
            - Attempt 2: after 1 second
            - Attempt 3: after 2 seconds

        On all retries exhausted, writes the payload to a local fallback file.

        Args:
            payload: The validated build event payload to transmit.
            api_key: API key for authentication (sent as ``X-API-Key`` header).

        Returns:
            PushResult with success status, HTTP code, and any fallback path.
        """
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": f"urgp-cli/{payload.cli_version}",
        }
        json_payload = payload.to_json_dict()

        last_error: str = ""

        for attempt in range(1, self._max_retries + 1):
            try:
                result = self._attempt_push(json_payload, headers, attempt)
                if result is not None:
                    return result
            except _RetryableError as exc:
                last_error = str(exc)
                if attempt < self._max_retries:
                    delay = _BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Attempt %d/%d failed: %s — retrying in %.1f seconds",
                        attempt,
                        self._max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "All %d attempts exhausted. Last error: %s",
                        self._max_retries,
                        exc,
                    )
            except _NonRetryableError as exc:
                # Client errors (4xx except 429) — no point retrying
                return PushResult(
                    success=False,
                    status_code=exc.status_code,
                    message=f"Server rejected payload: {exc}",
                )

        # All retries exhausted — write fallback file
        return self._write_fallback(payload, json_payload, last_error)

    def _attempt_push(
        self,
        json_payload: dict[str, object],
        headers: dict[str, str],
        attempt: int,
    ) -> PushResult | None:
        """Execute a single push attempt.

        Returns:
            PushResult if the attempt resolves definitively (success or client error).
            None should never be returned — raises _RetryableError or _NonRetryableError.

        Raises:
            _RetryableError: On transient failures (server errors, timeouts, connection errors).
            _NonRetryableError: On client errors (4xx status codes except 429).
        """
        try:
            response = httpx.post(
                self.ingest_url,
                json=json_payload,
                headers=headers,
                timeout=self._timeout,
            )

            status = response.status_code

            # Success cases
            if status in (200, 202):
                logger.info("Push successful (HTTP %d) on attempt %d", status, attempt)
                return PushResult(
                    success=True,
                    status_code=status,
                    message=f"Payload accepted (HTTP {status})",
                )

            # Retryable server errors
            if status in _RETRYABLE_STATUS_CODES:
                raise _RetryableError(f"HTTP {status}: {response.text[:200]}", status_code=status)

            # Rate limited — retryable
            if status == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                raise _RetryableError(
                    f"Rate limited (HTTP 429). Retry-After: {retry_after}",
                    status_code=429,
                )

            # Non-retryable client errors (400, 401, 403, 422, etc.)
            raise _NonRetryableError(
                f"HTTP {status}: {response.text[:500]}",
                status_code=status,
            )

        except httpx.ConnectError as exc:
            raise _RetryableError(f"Connection error: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise _RetryableError(f"Request timeout after {self._timeout}s: {exc}") from exc
        except httpx.HTTPError as exc:
            raise _RetryableError(f"HTTP error: {exc}") from exc

    @staticmethod
    def _write_fallback(
        payload: BuildEventPayload,
        json_payload: dict[str, object],
        last_error: str,
    ) -> PushResult:
        """Write the payload to a local fallback JSON file.

        The file is written to the current working directory with a
        deterministic name based on the build_id.

        Args:
            payload: The original payload (for build_id).
            json_payload: The serialized JSON dict.
            last_error: Description of the last failure.

        Returns:
            PushResult indicating failure with the fallback file path.
        """
        fallback_filename = f"urgp-fallback-{payload.build_id}.json"
        fallback_path = Path.cwd() / fallback_filename

        try:
            with open(fallback_path, "w", encoding="utf-8") as f:
                json.dump(json_payload, f, indent=2, default=str)
            logger.info("Fallback payload written to: %s", fallback_path)
        except OSError as exc:
            logger.error("Failed to write fallback file: %s", exc)
            return PushResult(
                success=False,
                status_code=None,
                message=f"All retries failed ({last_error}). Failed to write fallback: {exc}",
            )

        return PushResult(
            success=False,
            status_code=None,
            message=f"All retries failed ({last_error}). Payload saved to: {fallback_path}",
            fallback_path=str(fallback_path),
        )


class _RetryableError(Exception):
    """Raised for transient errors that should trigger a retry."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _NonRetryableError(Exception):
    """Raised for permanent errors that should NOT trigger a retry."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
