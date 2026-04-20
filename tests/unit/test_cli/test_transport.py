"""P1-2.T5: Test retry logic (mock server returning 500→503→200).

Verifies that the transport client correctly implements exponential
backoff retry on transient server errors and succeeds when the server
eventually responds.

Reference:
    - docs/07-implementation-plan.md § P1-2.T5
    - Requirements: R3.7 (retry with exponential backoff up to 3 attempts)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx

from urgp_cli.contracts.data_contract import (
    ArtifactPayload,
    ArtifactTypeEnum,
    BuildEventPayload,
    BuildTypeEnum,
    CommitHash,
)
from urgp_cli.transport.client import URGPClient


def _make_test_payload() -> BuildEventPayload:
    """Create a minimal valid payload for testing."""
    return BuildEventPayload(
        product_id="test-product",
        release="1.0.0",
        build_type=BuildTypeEnum.NIGHTLY,
        build_id="test-001",
        cli_version="0.1.0",
        commit_hashes=[CommitHash(repository="github.com/test/repo", hash="a" * 40)],
        artifacts=[
            ArtifactPayload(
                name="test.zip",
                type=ArtifactTypeEnum.GENERIC,
                storage_uri="file:///test.zip",
                sha256="b" * 64,
                size_bytes=1024,
            )
        ],
        timestamp=datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc),
    )


class TestRetryLogic:
    """Test retry behavior on transient server errors."""

    def test_success_on_first_attempt(self) -> None:
        """Immediate success (HTTP 200) — no retries needed."""
        client = URGPClient("http://localhost:8000")
        payload = _make_test_payload()

        mock_response = httpx.Response(200, json={"status": "accepted"})

        with patch("urgp_cli.transport.client.httpx.post", return_value=mock_response):
            result = client.push(payload, "test-api-key")

        assert result.success is True
        assert result.status_code == 200

    def test_success_on_accepted_202(self) -> None:
        """HTTP 202 (Accepted) is treated as success."""
        client = URGPClient("http://localhost:8000")
        payload = _make_test_payload()

        mock_response = httpx.Response(202, json={"status": "queued"})

        with patch("urgp_cli.transport.client.httpx.post", return_value=mock_response):
            result = client.push(payload, "test-api-key")

        assert result.success is True
        assert result.status_code == 202

    def test_retry_on_500_then_success(self) -> None:
        """Server returns 500 → 200: retries and succeeds."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_post = MagicMock(side_effect=[
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, json={"status": "accepted"}),
        ])

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
        ):
            result = client.push(payload, "test-api-key")

        assert result.success is True
        assert result.status_code == 200
        assert mock_post.call_count == 2

    def test_retry_500_503_then_success(self) -> None:
        """Server returns 500 → 503 → 200: retries twice and succeeds."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_post = MagicMock(side_effect=[
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(503, text="Service Unavailable"),
            httpx.Response(200, json={"status": "accepted"}),
        ])

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
        ):
            result = client.push(payload, "test-api-key")

        assert result.success is True
        assert result.status_code == 200
        assert mock_post.call_count == 3

    def test_all_retries_fail_creates_fallback(self) -> None:
        """All 3 attempts return 500: falls back to local file."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_post = MagicMock(side_effect=[
            httpx.Response(500, text="Server Error"),
            httpx.Response(500, text="Server Error"),
            httpx.Response(500, text="Server Error"),
        ])

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
        ):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.fallback_path is not None
        assert "urgp-fallback-test-001.json" in result.fallback_path
        assert mock_post.call_count == 3

    def test_no_retry_on_400(self) -> None:
        """HTTP 400 (Bad Request) — no retry, immediate failure."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_response = httpx.Response(400, text="Bad Request: invalid payload")

        with patch("urgp_cli.transport.client.httpx.post", return_value=mock_response):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.status_code == 400
        assert result.fallback_path is None

    def test_no_retry_on_401(self) -> None:
        """HTTP 401 (Unauthorized) — no retry."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_response = httpx.Response(401, text="Unauthorized")

        with patch("urgp_cli.transport.client.httpx.post", return_value=mock_response):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.status_code == 401

    def test_no_retry_on_422(self) -> None:
        """HTTP 422 (Unprocessable Entity) — no retry."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_response = httpx.Response(422, text="Validation Error")

        with patch("urgp_cli.transport.client.httpx.post", return_value=mock_response):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.status_code == 422


class TestClientConfiguration:
    """Test client configuration."""

    def test_ingest_url(self) -> None:
        """Ingest URL is correctly constructed."""
        client = URGPClient("https://urgp.internal")
        assert client.ingest_url == "https://urgp.internal/api/v1/ingest"

    def test_ingest_url_strips_trailing_slash(self) -> None:
        """Trailing slash in API URL is stripped."""
        client = URGPClient("https://urgp.internal/")
        assert client.ingest_url == "https://urgp.internal/api/v1/ingest"
