"""P1-2.T7: Test CLI parameter validation.

Verifies that the Typer CLI correctly validates parameters:
    - Missing required options
    - Invalid build type enum
    - Unpaired --commit-repo / --commit-hash
    - --help displays usage information
    - --version displays version string

Reference:
    - docs/07-implementation-plan.md § P1-2.T7
    - Requirements: R3.2, R3.10, R19.4
"""

from __future__ import annotations

from typer.testing import CliRunner

from urgp_cli import __version__
from urgp_cli.main import app

runner = CliRunner()


class TestVersionCommand:
    """Test --version flag."""

    def test_version_flag(self) -> None:
        """--version prints version and data contract version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert f"v{__version__}" in result.output
        assert "data-contract:" in result.output

    def test_short_version_flag(self) -> None:
        """-V prints version."""
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert f"v{__version__}" in result.output


class TestHelpOutput:
    """Test --help output for all commands."""

    def test_main_help(self) -> None:
        """Main help shows available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "push" in result.output
        assert "verify" in result.output

    def test_push_help(self) -> None:
        """Push help shows all required parameters."""
        result = runner.invoke(app, ["push", "--help"])
        assert result.exit_code == 0
        assert "--product" in result.output
        assert "--release" in result.output
        assert "--build-type" in result.output
        assert "--build-id" in result.output
        assert "--adapter" in result.output
        assert "--artifact" in result.output
        assert "--commit-repo" in result.output
        assert "--commit-hash" in result.output
        assert "--api-key" in result.output

    def test_verify_help(self) -> None:
        """Verify help shows required parameters."""
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0
        assert "--build-id" in result.output
        assert "--api-key" in result.output


class TestPushParameterValidation:
    """Test push command parameter validation."""

    def test_missing_product_fails(self) -> None:
        """Missing --product exits with error."""
        result = runner.invoke(
            app,
            [
                "push",
                "--release",
                "1.0",
                "--build-type",
                "nightly",
                "--build-id",
                "001",
                "--artifact",
                "README.md",
                "--commit-repo",
                "repo",
                "--commit-hash",
                "a" * 40,
                "--api-key",
                "test-key",
            ],
        )
        assert result.exit_code != 0

    def test_missing_release_fails(self) -> None:
        """Missing --release exits with error."""
        result = runner.invoke(
            app,
            [
                "push",
                "--product",
                "test",
                "--build-type",
                "nightly",
                "--build-id",
                "001",
                "--artifact",
                "README.md",
                "--commit-repo",
                "repo",
                "--commit-hash",
                "a" * 40,
                "--api-key",
                "test-key",
            ],
        )
        assert result.exit_code != 0

    def test_invalid_build_type_fails(self) -> None:
        """Invalid --build-type value exits with error."""
        result = runner.invoke(
            app,
            [
                "push",
                "--product",
                "test",
                "--release",
                "1.0",
                "--build-type",
                "invalid_type",
                "--build-id",
                "001",
                "--artifact",
                "README.md",
                "--commit-repo",
                "repo",
                "--commit-hash",
                "a" * 40,
                "--api-key",
                "test-key",
            ],
        )
        assert result.exit_code != 0

    def test_unpaired_commit_repo_hash_fails(self, tmp_path: object) -> None:
        """Unpaired --commit-repo without matching --commit-hash fails."""
        result = runner.invoke(
            app,
            [
                "push",
                "--product",
                "test",
                "--release",
                "1.0",
                "--build-type",
                "nightly",
                "--build-id",
                "001",
                "--artifact",
                "README.md",
                "--commit-repo",
                "repo1",
                "--commit-repo",
                "repo2",
                "--commit-hash",
                "a" * 40,
                "--api-key",
                "test-key",
            ],
        )
        # Should fail because 2 repos but only 1 hash
        assert result.exit_code != 0

    def test_nonexistent_artifact_fails(self) -> None:
        """Non-existent artifact file exits with error."""
        result = runner.invoke(
            app,
            [
                "push",
                "--product",
                "test",
                "--release",
                "1.0",
                "--build-type",
                "nightly",
                "--build-id",
                "001",
                "--artifact",
                "/nonexistent/path/file.zip",
                "--commit-repo",
                "repo",
                "--commit-hash",
                "a" * 40,
                "--api-key",
                "test-key",
            ],
        )
        assert result.exit_code != 0

    def test_missing_api_key_fails(self) -> None:
        """Missing --api-key exits with error."""
        result = runner.invoke(
            app,
            [
                "push",
                "--product",
                "test",
                "--release",
                "1.0",
                "--build-type",
                "nightly",
                "--build-id",
                "001",
                "--artifact",
                "README.md",
                "--commit-repo",
                "repo",
                "--commit-hash",
                "a" * 40,
            ],
        )
        assert result.exit_code != 0


class TestNoArgsShowsHelp:
    """Test that running without arguments shows help."""

    def test_no_args_shows_help(self) -> None:
        """Running urgp-cli without arguments shows help."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "push" in result.output or "Usage" in result.output
