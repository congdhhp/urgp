"""SHA-256 checksum computation with streaming support.

Computes SHA-256 checksums efficiently for files of any size using
streaming I/O. Files are read in chunks to keep memory usage constant
regardless of file size (supports files up to 2GB+).

Reference:
    - docs/07-implementation-plan.md § P1-2.2
    - Requirement R3.5: SHA-256 checksums for all artifacts
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

# 8 KB read buffer — balanced between syscall overhead and memory usage
_DEFAULT_BUFFER_SIZE = 8 * 1024

# Progress reporting threshold: only report for files > 100 MB
_PROGRESS_THRESHOLD_BYTES = 100 * 1024 * 1024


def compute_sha256(
    file_path: Path,
    *,
    buffer_size: int = _DEFAULT_BUFFER_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    """Compute SHA-256 checksum of a file using streaming I/O.

    Reads the file in fixed-size chunks to maintain constant memory usage.
    Supports files of arbitrary size (tested up to 2GB+).

    Args:
        file_path: Path to the file to checksum.
        buffer_size: Read buffer size in bytes (default: 8 KB).
        progress_callback: Optional callback ``(bytes_read, total_bytes)``
            invoked after each chunk is processed. Useful for progress bars.

    Returns:
        Lowercase hex digest string matching ``^[a-f0-9]{64}$``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the path is not a regular file.
        OSError: If the file cannot be read.
    """
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)
    if not file_path.is_file():
        msg = f"Path is not a file: {file_path}"
        raise ValueError(msg)

    total_size = file_path.stat().st_size
    sha256_hash = hashlib.sha256()
    bytes_read = 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(buffer_size)
            if not chunk:
                break
            sha256_hash.update(chunk)
            bytes_read += len(chunk)

            if progress_callback is not None:
                progress_callback(bytes_read, total_size)

    return sha256_hash.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 checksum of raw bytes.

    Utility function for testing and small in-memory payloads.

    Args:
        data: Raw bytes to checksum.

    Returns:
        Lowercase hex digest string.
    """
    return hashlib.sha256(data).hexdigest()


def should_report_progress(file_path: Path) -> bool:
    """Check if a file is large enough to warrant progress reporting.

    Args:
        file_path: Path to check.

    Returns:
        True if file is larger than 100 MB.
    """
    try:
        return file_path.stat().st_size > _PROGRESS_THRESHOLD_BYTES
    except OSError:
        return False
