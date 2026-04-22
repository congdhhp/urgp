"""Shared fixtures for CLI tests.

Creates temporary test files (binary, .zip, .tar.gz, P2 repo) for adapter
and checksum testing. Fixtures are session-scoped where possible to avoid
repeated I/O.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_binary_file(tmp_path: Path) -> Path:
    """Create a small binary file for GenericAdapter tests."""
    path = tmp_path / "sample_binary.bin"
    # Write 1 KB of deterministic binary data
    path.write_bytes(bytes(range(256)) * 4)
    return path


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    """Create a sample text file."""
    path = tmp_path / "readme.txt"
    path.write_text("Hello URGP\nThis is a test file.\n", encoding="utf-8")
    return path


@pytest.fixture
def sample_zip_file(tmp_path: Path) -> Path:
    """Create a ZIP archive with known contents."""
    zip_path = tmp_path / "sample_archive.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file1.txt", "Content of file 1")
        zf.writestr("file2.txt", "Content of file 2")
        zf.writestr("subdir/file3.txt", "Content of file 3 in subdir")
    return zip_path


@pytest.fixture
def sample_tar_gz_file(tmp_path: Path) -> Path:
    """Create a .tar.gz archive with known contents."""
    tar_path = tmp_path / "sample_archive.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        # Add string content as tarfile members
        for name, content in [
            ("file1.txt", b"Content of file 1"),
            ("file2.txt", b"Content of file 2"),
        ]:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
    return tar_path


@pytest.fixture
def empty_file(tmp_path: Path) -> Path:
    """Create an empty file (should fail validation)."""
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    return path


@pytest.fixture
def sample_content_xml() -> bytes:
    """Generate a minimal Eclipse P2 content.xml for testing."""
    # Build a minimal P2 metadata repository XML
    repository = Element("repository")
    repository.set("name", "Test P2 Repository")
    repository.set("type", "org.eclipse.equinox.internal.p2.metadata.repository.LocalMetadataRepository")
    repository.set("version", "1.0.0")

    units = SubElement(repository, "units")
    units.set("size", "4")

    # Feature group IU
    _add_iu(
        units,
        "com.example.feature.feature.group",
        "1.0.0.202603300001",
        [
            ("org.eclipse.platform.feature.group", "[4.0.0,5.0.0)"),
        ],
    )

    # Feature jar IU
    _add_iu(units, "com.example.feature.feature.jar", "1.0.0.202603300001", [])

    # Plugin IU
    _add_iu(
        units,
        "com.example.plugin",
        "1.0.0.202603300001",
        [
            ("org.eclipse.core.runtime", "[3.0.0,4.0.0)"),
        ],
    )

    # Another plugin
    _add_iu(units, "com.example.utils", "1.0.0.202603300001", [])

    return tostring(repository, encoding="unicode").encode("utf-8")


def _add_iu(
    parent: Element,
    iu_id: str,
    version: str,
    requires: list[tuple[str, str]],
) -> None:
    """Helper to add an Installable Unit to the XML tree."""
    unit = SubElement(parent, "unit")
    unit.set("id", iu_id)
    unit.set("version", version)

    if requires:
        req_el = SubElement(unit, "requires")
        req_el.set("size", str(len(requires)))
        for name, version_range in requires:
            req = SubElement(req_el, "required")
            req.set("namespace", "osgi.bundle")
            req.set("name", name)
            req.set("range", version_range)


@pytest.fixture
def sample_p2_repo_zip(tmp_path: Path, sample_content_xml: bytes) -> Path:
    """Create a ZIP file containing a P2 repository structure."""
    zip_path = tmp_path / "sample_p2_repo.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", sample_content_xml)
        zf.writestr("artifacts.xml", "<artifacts/>")
        # Add a fake plugin JAR
        zf.writestr("plugins/com.example.plugin_1.0.0.jar", b"fake-plugin-bytes")
    return zip_path


@pytest.fixture
def sample_p2_repo_with_content_jar(tmp_path: Path, sample_content_xml: bytes) -> Path:
    """Create a P2 repo ZIP where content.xml is inside content.jar."""
    zip_path = tmp_path / "p2_repo_with_content_jar.zip"

    # First, create an inner content.jar containing content.xml
    content_jar_buf = io.BytesIO()
    with zipfile.ZipFile(content_jar_buf, "w") as jar:
        jar.writestr("content.xml", sample_content_xml)
    content_jar_bytes = content_jar_buf.getvalue()

    # Then create the outer ZIP with content.jar inside
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("content.jar", content_jar_bytes)
        zf.writestr("artifacts.jar", b"fake-artifacts-jar")
    return zip_path


@pytest.fixture
def sample_composite_p2_repo_with_content_jar(tmp_path: Path, sample_content_xml: bytes) -> Path:
    """Create a composite P2 repo ZIP where content.xml is inside compositeContent.jar."""
    zip_path = tmp_path / "composite_p2_repo_with_content_jar.zip"

    composite_content_jar_buf = io.BytesIO()
    with zipfile.ZipFile(composite_content_jar_buf, "w") as jar:
        jar.writestr("content.xml", sample_content_xml)
    composite_content_jar_bytes = composite_content_jar_buf.getvalue()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("compositeContent.jar", composite_content_jar_bytes)
        zf.writestr("compositeArtifacts.jar", b"fake-composite-artifacts-jar")

    return zip_path


@pytest.fixture
def invalid_zip_file(tmp_path: Path) -> Path:
    """Create a file that is not a valid ZIP."""
    path = tmp_path / "invalid.zip"
    path.write_bytes(b"This is not a ZIP file at all")
    return path


@pytest.fixture
def non_p2_zip_file(tmp_path: Path) -> Path:
    """Create a valid ZIP that is NOT a P2 repository."""
    zip_path = tmp_path / "not_p2.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("some_file.txt", "Not a P2 repository")
    return zip_path


@pytest.fixture
def known_content_file(tmp_path: Path) -> Path:
    """Create a file with known content for SHA-256 verification.

    Content: b"urgp-test-content"
    Expected SHA-256: computed at runtime for self-verification.
    """
    path = tmp_path / "known_content.txt"
    path.write_bytes(b"urgp-test-content")
    return path
