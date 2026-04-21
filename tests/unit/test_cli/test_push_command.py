"""Targeted tests for push command helpers and adapter validation flow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from urgp_cli.commands.push import _build_storage_uri, _resolve_artifact_type
from urgp_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text for reliable assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestPushHelpers:
    """Test internal push helper logic."""

    def test_build_storage_uri_uses_file_uri_for_local_paths(self, tmp_path: Path) -> None:
        """Local artifact storage URIs should use Path.as_uri()."""
        artifact_path = tmp_path / "build-output.zip"
        artifact_path.write_text("test", encoding="utf-8")

        assert _build_storage_uri(artifact_path, "") == artifact_path.resolve().as_uri()

    def test_build_storage_uri_appends_encoded_filename(self, tmp_path: Path) -> None:
        """Remote storage prefixes should get one encoded file name appended."""
        artifact_path = tmp_path / "build output.zip"
        artifact_path.write_text("test", encoding="utf-8")

        storage_uri = _build_storage_uri(artifact_path, "https://artifacts.example.com/releases")

        assert storage_uri == "https://artifacts.example.com/releases/build%20output.zip"

    def test_resolve_artifact_type_rejects_unknown_adapter_type(self) -> None:
        """Unknown adapter types must fail fast instead of silently degrading."""
        with pytest.raises(ValueError, match="unsupported artifact type"):
            _resolve_artifact_type("future_adapter")


class TestPushValidationFlow:
    """Test high-level push validation behavior."""

    def test_push_rejects_artifact_that_fails_adapter_validation(self, tmp_path: Path) -> None:
        """Push should fail before transmission if adapter validation fails."""
        artifact_path = tmp_path / "empty.bin"
        artifact_path.write_bytes(b"")

        result = runner.invoke(
            app,
            [
                "push",
                "--product",
                "test-product",
                "--release",
                "1.0.0",
                "--build-type",
                "nightly",
                "--build-id",
                "build-001",
                "--artifact",
                str(artifact_path),
                "--commit-repo",
                "github.com/example/repo",
                "--commit-hash",
                "a" * 40,
                "--api-key",
                "test-api-key",
            ],
        )

        output = _strip_ansi(result.output)
        assert result.exit_code == 2
        assert "Artifact failed generic adapter validation" in output
