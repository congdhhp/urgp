"""P1-2.T2: Test EclipseP2Adapter with sample S32 P2 repository .zip.

Tests that the EclipseP2Adapter correctly parses P2 repository metadata
from content.xml, handles content.jar wrapping, and rejects non-P2 archives.

Reference:
    - docs/07-implementation-plan.md § P1-2.T2
"""

from __future__ import annotations

from pathlib import Path

from urgp_cli.adapters.eclipse_p2 import EclipseP2Adapter


class TestEclipseP2AdapterMetadata:
    """Test P2 metadata extraction."""

    def setup_method(self) -> None:
        self.adapter = EclipseP2Adapter()

    def test_adapter_type(self) -> None:
        """Adapter type should be 'eclipse_p2'."""
        assert self.adapter.adapter_type == "eclipse_p2"

    def test_extract_from_content_xml(self, sample_p2_repo_zip: Path) -> None:
        """P2 ZIP with direct content.xml: extracts IUs, features, plugins."""
        result = self.adapter.extract_metadata(sample_p2_repo_zip)

        assert result.errors == []
        meta = result.metadata
        assert meta["iu_count"] == 4
        assert meta["feature_count"] == 2  # feature.group + feature.jar
        assert meta["plugin_count"] == 2  # com.example.plugin + com.example.utils

        # Check feature list
        features = meta["features"]
        assert isinstance(features, list)
        feature_ids = [f["id"] for f in features]
        assert "com.example.feature.feature.group" in feature_ids
        assert "com.example.feature.feature.jar" in feature_ids

        # Check plugin list
        plugins = meta["plugins"]
        assert isinstance(plugins, list)
        plugin_ids = [p["id"] for p in plugins]
        assert "com.example.plugin" in plugin_ids

    def test_extract_from_content_jar(self, sample_p2_repo_with_content_jar: Path) -> None:
        """P2 ZIP with content.jar: correctly unwraps and parses content.xml."""
        result = self.adapter.extract_metadata(sample_p2_repo_with_content_jar)

        assert result.errors == []
        assert result.metadata["iu_count"] == 4

    def test_extract_from_composite_content_jar(self, sample_composite_p2_repo_with_content_jar: Path) -> None:
        """Composite P2 ZIP with compositeContent.jar: correctly unwraps and parses content.xml."""
        result = self.adapter.extract_metadata(sample_composite_p2_repo_with_content_jar)

        assert result.errors == []
        assert result.metadata["iu_count"] == 4

    def test_dependencies_extracted(self, sample_p2_repo_zip: Path) -> None:
        """Dependencies (required elements) are extracted from content.xml."""
        result = self.adapter.extract_metadata(sample_p2_repo_zip)

        assert len(result.dependencies) > 0
        assert "org.eclipse.platform.feature.group" in result.dependencies
        assert "org.eclipse.core.runtime" in result.dependencies

    def test_non_p2_zip_returns_errors(self, non_p2_zip_file: Path) -> None:
        """Non-P2 ZIP returns errors (no content.xml found)."""
        result = self.adapter.extract_metadata(non_p2_zip_file)

        assert len(result.errors) > 0
        assert "content.xml" in result.errors[0].lower() or "not a valid P2" in result.errors[0]

    def test_invalid_zip_returns_errors(self, invalid_zip_file: Path) -> None:
        """Invalid (corrupted) ZIP returns errors."""
        result = self.adapter.extract_metadata(invalid_zip_file)

        assert len(result.errors) > 0


class TestEclipseP2AdapterValidation:
    """Test P2 artifact validation."""

    def setup_method(self) -> None:
        self.adapter = EclipseP2Adapter()

    def test_valid_p2_repo(self, sample_p2_repo_zip: Path) -> None:
        """Valid P2 repository ZIP passes validation."""
        assert self.adapter.validate_artifact(sample_p2_repo_zip) is True

    def test_p2_with_content_jar(self, sample_p2_repo_with_content_jar: Path) -> None:
        """P2 repo with content.jar passes validation."""
        assert self.adapter.validate_artifact(sample_p2_repo_with_content_jar) is True

    def test_composite_p2_with_content_jar(self, sample_composite_p2_repo_with_content_jar: Path) -> None:
        """Composite P2 repo with compositeContent.jar passes validation."""
        assert self.adapter.validate_artifact(sample_composite_p2_repo_with_content_jar) is True

    def test_non_p2_zip_fails(self, non_p2_zip_file: Path) -> None:
        """Non-P2 ZIP fails validation."""
        assert self.adapter.validate_artifact(non_p2_zip_file) is False

    def test_invalid_zip_fails(self, invalid_zip_file: Path) -> None:
        """Invalid ZIP file fails validation."""
        assert self.adapter.validate_artifact(invalid_zip_file) is False

    def test_nonexistent_file_fails(self, tmp_path: Path) -> None:
        """Non-existent file fails validation."""
        assert self.adapter.validate_artifact(tmp_path / "missing.zip") is False

    def test_non_zip_file_fails(self, sample_binary_file: Path) -> None:
        """Non-ZIP binary file fails P2 validation."""
        assert self.adapter.validate_artifact(sample_binary_file) is False
