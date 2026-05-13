"""P1-2.T1: Test GenericAdapter with sample files (binary, .zip, .tar.gz).

Tests that the GenericAdapter correctly extracts file-level metadata
for different artifact types: binary files, ZIP archives, and tar.gz archives.

Reference:
    - docs/07-implementation-plan.md § P1-2.T1
"""

from __future__ import annotations

from pathlib import Path

import pytest

from urgp_cli.adapters.generic import GenericAdapter


class TestGenericAdapterMetadata:
    """Test metadata extraction for various file types."""

    def setup_method(self) -> None:
        self.adapter = GenericAdapter()

    def test_adapter_type(self) -> None:
        """Adapter type should be 'generic'."""
        assert self.adapter.adapter_type == "generic"

    def test_binary_file_metadata(self, sample_binary_file: Path) -> None:
        """Binary file: extracts size, MIME type, extension, last_modified."""
        result = self.adapter.extract_metadata(sample_binary_file)

        assert result.metadata["file_size_bytes"] == 1024
        assert result.metadata["file_extension"] == ".bin"
        assert "mime_type" in result.metadata
        assert "last_modified" in result.metadata
        assert result.errors == []

    def test_text_file_metadata(self, sample_text_file: Path) -> None:
        """Text file: MIME type should be text/plain."""
        result = self.adapter.extract_metadata(sample_text_file)

        assert result.metadata["mime_type"] == "text/plain"
        assert result.metadata["file_extension"] == ".txt"
        assert result.metadata["file_size_bytes"] > 0

    def test_zip_file_metadata(self, sample_zip_file: Path) -> None:
        """ZIP file: extracts archive-specific metadata (entry count, compression)."""
        result = self.adapter.extract_metadata(sample_zip_file)

        assert result.metadata["archive_type"] == "zip"
        assert result.metadata["entry_count"] == 3
        assert "total_compressed_bytes" in result.metadata
        assert "total_uncompressed_bytes" in result.metadata
        assert "compression_ratio" in result.metadata
        assert isinstance(result.metadata["compression_ratio"], float)

    def test_tar_gz_file_metadata(self, sample_tar_gz_file: Path) -> None:
        """TAR.GZ file: extracts archive-specific metadata."""
        result = self.adapter.extract_metadata(sample_tar_gz_file)

        assert result.metadata["archive_type"] == "tar"
        assert result.metadata["entry_count"] == 2
        assert "total_uncompressed_bytes" in result.metadata

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Artifact not found"):
            self.adapter.extract_metadata(tmp_path / "nonexistent.bin")

    def test_directory_raises(self, tmp_path: Path) -> None:
        """Directory path raises ValueError."""
        with pytest.raises(ValueError, match="not a file"):
            self.adapter.extract_metadata(tmp_path)


class TestGenericAdapterValidation:
    """Test artifact validation logic."""

    def setup_method(self) -> None:
        self.adapter = GenericAdapter()

    def test_valid_binary_file(self, sample_binary_file: Path) -> None:
        """Valid binary file passes validation."""
        assert self.adapter.validate_artifact(sample_binary_file) is True

    def test_valid_zip_file(self, sample_zip_file: Path) -> None:
        """Valid ZIP file passes validation."""
        assert self.adapter.validate_artifact(sample_zip_file) is True

    def test_empty_file_fails(self, empty_file: Path) -> None:
        """Empty file fails validation."""
        assert self.adapter.validate_artifact(empty_file) is False

    def test_nonexistent_file_fails(self, tmp_path: Path) -> None:
        """Non-existent file fails validation."""
        assert self.adapter.validate_artifact(tmp_path / "missing.bin") is False

    def test_directory_fails(self, tmp_path: Path) -> None:
        """Directory fails validation (not a file)."""
        assert self.adapter.validate_artifact(tmp_path) is False
