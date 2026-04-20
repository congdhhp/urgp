"""P1-2.T6: Test fallback file creation on network failure.

Verifies that when all transmission attempts fail, the CLI correctly
writes the Data Contract payload to a local JSON file for later recovery.

Reference:
    - docs/07-implementation-plan.md § P1-2.T6
    - Requirements: R3.8 (write to local disk on failure)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
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


def _make_test_payload(build_id: str = "fallback-test-001") -> BuildEventPayload:
    """Create a valid payload for fallback testing."""
    return BuildEventPayload(
        product_id="test-product",
        release="1.0.0",
        build_type=BuildTypeEnum.NIGHTLY,
        build_id=build_id,
        cli_version="0.1.0",
        commit_hashes=[CommitHash(repository="github.com/test/repo", hash="a" * 40)],
        artifacts=[
            ArtifactPayload(
                name="test-artifact.zip",
                type=ArtifactTypeEnum.GENERIC,
                storage_uri="file:///test-artifact.zip",
                sha256="c" * 64,
                size_bytes=2048,
            )
        ],
        timestamp=datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc),
    )


class TestFallbackFileCreation:
    """Test fallback file creation on complete transmission failure."""

    def test_fallback_file_created_on_connection_error(self, tmp_path: Path) -> None:
        """Connection error (server unreachable) creates fallback file."""
        client = URGPClient("http://unreachable.local:9999", max_retries=2)
        payload = _make_test_payload(build_id="conn-err-001")

        mock_post = MagicMock(side_effect=httpx.ConnectError("Connection refused"))

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
            patch("urgp_cli.transport.client.Path.cwd", return_value=tmp_path),
        ):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.fallback_path is not None
        assert "urgp-fallback-conn-err-001.json" in result.fallback_path

        # Verify file exists and contains valid JSON
        fallback_file = Path(result.fallback_path)
        assert fallback_file.exists()

        with open(fallback_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["product_id"] == "test-product"
        assert data["build_id"] == "conn-err-001"

    def test_fallback_file_created_on_server_errors(self, tmp_path: Path) -> None:
        """All retries returning 500 creates fallback file."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload(build_id="server-err-001")

        mock_post = MagicMock(side_effect=[
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(500, text="Internal Server Error"),
        ])

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
            patch("urgp_cli.transport.client.Path.cwd", return_value=tmp_path),
        ):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.fallback_path is not None

        fallback_file = Path(result.fallback_path)
        assert fallback_file.exists()

    def test_fallback_file_contains_complete_payload(self, tmp_path: Path) -> None:
        """Fallback file contains the complete, valid Data Contract payload."""
        client = URGPClient("http://localhost:8000", max_retries=1)
        payload = _make_test_payload(build_id="complete-payload-001")

        mock_post = MagicMock(return_value=httpx.Response(502, text="Bad Gateway"))

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
            patch("urgp_cli.transport.client.Path.cwd", return_value=tmp_path),
        ):
            result = client.push(payload, "test-api-key")

        assert result.fallback_path is not None
        with open(result.fallback_path, encoding="utf-8") as f:
            data = json.load(f)

        # Verify all required fields are present
        assert "product_id" in data
        assert "release" in data
        assert "build_type" in data
        assert "build_id" in data
        assert "cli_version" in data
        assert "commit_hashes" in data
        assert "artifacts" in data
        assert "timestamp" in data

        # Verify artifact details
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["sha256"] == "c" * 64
        assert data["artifacts"][0]["name"] == "test-artifact.zip"

    def test_fallback_filename_pattern(self, tmp_path: Path) -> None:
        """Fallback filename follows the pattern urgp-fallback-{build_id}.json."""
        client = URGPClient("http://localhost:8000", max_retries=1)
        payload = _make_test_payload(build_id="my-custom-build-42")

        mock_post = MagicMock(return_value=httpx.Response(503, text="Unavailable"))

        with (
            patch("urgp_cli.transport.client.httpx.post", mock_post),
            patch("urgp_cli.transport.client.time.sleep"),
            patch("urgp_cli.transport.client.Path.cwd", return_value=tmp_path),
        ):
            result = client.push(payload, "test-api-key")

        assert result.fallback_path is not None
        filename = os.path.basename(result.fallback_path)
        assert filename == "urgp-fallback-my-custom-build-42.json"

    def test_no_fallback_on_client_errors(self) -> None:
        """Client errors (4xx) do NOT create fallback files."""
        client = URGPClient("http://localhost:8000", max_retries=3)
        payload = _make_test_payload()

        mock_post = MagicMock(return_value=httpx.Response(400, text="Bad Request"))

        with patch("urgp_cli.transport.client.httpx.post", mock_post):
            result = client.push(payload, "test-api-key")

        assert result.success is False
        assert result.fallback_path is None
