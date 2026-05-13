"""P1-2.T3: Test SHA-256 computation accuracy.

Verifies that the streaming SHA-256 checksum computation produces
correct results by comparing against Python's hashlib reference
implementation.

Reference:
    - docs/07-implementation-plan.md § P1-2.T3
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from urgp_cli.checksum import compute_sha256, compute_sha256_bytes, should_report_progress


class TestSHA256Accuracy:
    """Test SHA-256 checksum correctness."""

    def test_known_content(self, known_content_file: Path) -> None:
        """SHA-256 of known content matches hashlib reference."""
        expected = hashlib.sha256(b"urgp-test-content").hexdigest()
        actual = compute_sha256(known_content_file)
        assert actual == expected

    def test_binary_file(self, sample_binary_file: Path) -> None:
        """SHA-256 of binary file matches hashlib reference."""
        expected = hashlib.sha256(sample_binary_file.read_bytes()).hexdigest()
        actual = compute_sha256(sample_binary_file)
        assert actual == expected

    def test_zip_file(self, sample_zip_file: Path) -> None:
        """SHA-256 of ZIP file matches hashlib reference."""
        expected = hashlib.sha256(sample_zip_file.read_bytes()).hexdigest()
        actual = compute_sha256(sample_zip_file)
        assert actual == expected

    def test_deterministic(self, sample_binary_file: Path) -> None:
        """Same file always produces the same checksum."""
        result1 = compute_sha256(sample_binary_file)
        result2 = compute_sha256(sample_binary_file)
        assert result1 == result2

    def test_output_format(self, sample_binary_file: Path) -> None:
        """Output is 64 lowercase hex characters."""
        result = compute_sha256(sample_binary_file)
        assert len(result) == 64
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_content_bytes(self) -> None:
        """SHA-256 of empty bytes matches known value."""
        expected = hashlib.sha256(b"").hexdigest()
        actual = compute_sha256_bytes(b"")
        assert actual == expected

    def test_compute_bytes_utility(self) -> None:
        """compute_sha256_bytes matches hashlib for arbitrary bytes."""
        data = b"hello world, this is URGP"
        expected = hashlib.sha256(data).hexdigest()
        actual = compute_sha256_bytes(data)
        assert actual == expected


class TestSHA256ProgressCallback:
    """Test progress callback behavior."""

    def test_callback_invoked(self, sample_binary_file: Path) -> None:
        """Progress callback is invoked during hashing."""
        calls: list[tuple[int, int]] = []

        def callback(bytes_read: int, total: int) -> None:
            calls.append((bytes_read, total))

        compute_sha256(sample_binary_file, progress_callback=callback)

        assert len(calls) > 0
        # Last call should have bytes_read == total
        assert calls[-1][0] == calls[-1][1]

    def test_callback_total_matches_file_size(self, sample_binary_file: Path) -> None:
        """Progress callback reports correct total file size."""
        expected_size = sample_binary_file.stat().st_size
        totals: list[int] = []

        def callback(bytes_read: int, total: int) -> None:
            totals.append(total)

        compute_sha256(sample_binary_file, progress_callback=callback)

        assert all(t == expected_size for t in totals)


class TestSHA256ErrorHandling:
    """Test error handling for checksum computation."""

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            compute_sha256(tmp_path / "nonexistent.txt")

    def test_directory_raises(self, tmp_path: Path) -> None:
        """Directory path raises ValueError."""
        with pytest.raises(ValueError, match="not a file"):
            compute_sha256(tmp_path)


class TestShouldReportProgress:
    """Test progress reporting threshold check."""

    def test_small_file_no_progress(self, sample_binary_file: Path) -> None:
        """Small files (< 100 MB) should not report progress."""
        assert should_report_progress(sample_binary_file) is False

    def test_nonexistent_file_no_progress(self, tmp_path: Path) -> None:
        """Non-existent files return False."""
        assert should_report_progress(tmp_path / "missing.bin") is False
