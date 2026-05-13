"""Behavioral tests for the verify CLI command."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from urgp_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text for reliable assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _make_mock_http_client(response: httpx.Response) -> MagicMock:
    """Create an httpx.Client mock that acts as a context manager."""
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.return_value = response
    return client


class TestVerifyCommand:
    """Test verify command behavior against the verification API."""

    def test_verify_uses_integrity_endpoint(self) -> None:
        """Verify should call POST /api/v1/builds/{id}/verify and report success."""
        response = httpx.Response(
            200,
            json={
                "verified": True,
                "traceability_incomplete": False,
                "artifacts": [
                    {
                        "name": "artifact.zip",
                        "type": "generic",
                        "sha256": "a" * 64,
                        "valid": True,
                    }
                ],
            },
        )
        mock_client = _make_mock_http_client(response)

        with patch("urgp_cli.commands.verify.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["verify", "--build-id", "260330", "--api-key", "test-key"])

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "Integrity verification passed" in output
        assert "valid" in output
        assert mock_client.post.call_args.args[0].endswith("/api/v1/builds/260330/verify")

    def test_verify_passes_optional_product_scope(self) -> None:
        """Optional product scope should be sent in the verification request body."""
        response = httpx.Response(200, json={"verified": True, "artifacts": []})
        mock_client = _make_mock_http_client(response)

        with patch("urgp_cli.commands.verify.httpx.Client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "verify",
                    "--build-id",
                    "260330",
                    "--product",
                    "S32_IDE",
                    "--api-key",
                    "test-key",
                ],
            )

        assert result.exit_code == 0
        assert mock_client.post.call_args.kwargs["json"] == {"product_id": "S32_IDE"}

    def test_verify_endpoint_unavailable_returns_error(self) -> None:
        """Server responses indicating no verify endpoint should fail clearly."""
        response = httpx.Response(405, json={"detail": "Method Not Allowed"})
        mock_client = _make_mock_http_client(response)

        with patch("urgp_cli.commands.verify.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["verify", "--build-id", "260330", "--api-key", "test-key"])

        output = _strip_ansi(result.output)
        assert result.exit_code == 1
        assert "endpoint is not available" in output

    def test_verify_inconclusive_response_fails(self) -> None:
        """A response without a clear verification verdict must fail closed."""
        response = httpx.Response(
            200,
            json={
                "traceability_incomplete": False,
                "artifacts": [
                    {
                        "name": "artifact.zip",
                        "type": "generic",
                        "sha256": "a" * 64,
                    }
                ],
            },
        )
        mock_client = _make_mock_http_client(response)

        with patch("urgp_cli.commands.verify.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["verify", "--build-id", "260330", "--api-key", "test-key"])

        output = _strip_ansi(result.output)
        assert result.exit_code == 1
        assert "inconclusive result" in output
        assert "unknown" in output
