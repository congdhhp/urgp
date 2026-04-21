"""Generic adapter — extracts basic file metadata for any artifact type.

The GenericAdapter is the default adapter used when no technology-specific
adapter is configured. It extracts file-level metadata applicable to any
artifact: file size, MIME type, last-modified timestamp, and archive
statistics for ZIP/tar files.

Reference:
    - docs/05-technical-design.md § Adapter Interface
    - docs/07-implementation-plan.md § P1-2.3
"""

from __future__ import annotations

import mimetypes
import os
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from urgp_cli.adapters.base import AdapterResult, BaseAdapter


class GenericAdapter(BaseAdapter):
    """Default adapter extracting basic file metadata.

    Extracts:
        - File size (bytes)
        - MIME type (inferred from extension)
        - Last-modified timestamp (ISO 8601)
        - File extension
        - Archive statistics (entry count, compression ratio) for ZIP/tar.gz
    """

    @property
    def adapter_type(self) -> str:
        return "generic"

    def extract_metadata(self, artifact_path: Path) -> AdapterResult:
        """Extract generic file metadata from any artifact.

        Args:
            artifact_path: Path to the artifact file.

        Returns:
            AdapterResult with file-level metadata.
        """
        self._ensure_file_exists(artifact_path)

        stat = artifact_path.stat()
        mime_type, _ = mimetypes.guess_type(str(artifact_path))

        metadata: dict[str, object] = {
            "file_size_bytes": stat.st_size,
            "mime_type": mime_type or "application/octet-stream",
            "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "file_extension": artifact_path.suffix.lower(),
        }

        errors: list[str] = []

        # Enrich with archive-specific metadata
        if zipfile.is_zipfile(str(artifact_path)):
            try:
                archive_meta = self._extract_zip_metadata(artifact_path)
                metadata.update(archive_meta)
            except Exception as exc:
                errors.append(f"Failed to extract ZIP metadata: {exc}")
        elif tarfile.is_tarfile(str(artifact_path)):
            try:
                archive_meta = self._extract_tar_metadata(artifact_path)
                metadata.update(archive_meta)
            except Exception as exc:
                errors.append(f"Failed to extract tar metadata: {exc}")

        return AdapterResult(metadata=metadata, errors=errors)

    def validate_artifact(self, artifact_path: Path) -> bool:
        """Validate that the file exists, is readable, and is not empty.

        Args:
            artifact_path: Path to the artifact file.

        Returns:
            True if the artifact is valid for generic processing.
        """
        try:
            self._ensure_file_exists(artifact_path)
        except (FileNotFoundError, ValueError):
            return False

        # Reject empty files
        if artifact_path.stat().st_size == 0:
            return False

        # Check read permission
        return os.access(artifact_path, os.R_OK)

    @staticmethod
    def _extract_zip_metadata(artifact_path: Path) -> dict[str, object]:
        """Extract metadata from a ZIP archive."""
        with zipfile.ZipFile(artifact_path, "r") as zf:
            entries = zf.infolist()
            total_compressed = sum(e.compress_size for e in entries)
            total_uncompressed = sum(e.file_size for e in entries)

            compression_ratio = (
                round(1.0 - (total_compressed / total_uncompressed), 4) if total_uncompressed > 0 else 0.0
            )

            return {
                "archive_type": "zip",
                "entry_count": len(entries),
                "total_compressed_bytes": total_compressed,
                "total_uncompressed_bytes": total_uncompressed,
                "compression_ratio": compression_ratio,
            }

    @staticmethod
    def _extract_tar_metadata(artifact_path: Path) -> dict[str, object]:
        """Extract metadata from a tar (or tar.gz/tar.bz2) archive."""
        with tarfile.open(artifact_path, "r:*") as tf:
            members = tf.getmembers()
            total_size = sum(m.size for m in members if m.isfile())

            return {
                "archive_type": "tar",
                "entry_count": len(members),
                "total_uncompressed_bytes": total_size,
            }
