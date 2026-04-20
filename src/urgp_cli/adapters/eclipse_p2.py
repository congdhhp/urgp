"""Eclipse P2 adapter — extracts metadata from Eclipse P2 repository artifacts.

Parses P2 repository ZIP files to extract Installable Unit (IU) metadata
from ``content.xml`` or ``content.jar``. This adapter is critical for
the S32 Design Studio use case, which packages Eclipse-based IDE plugins
as P2 repositories.

Reference:
    - docs/05-technical-design.md § Adapter Interface
    - docs/07-implementation-plan.md § P1-2.3
    - Eclipse P2 Repository Format: https://wiki.eclipse.org/Equinox/p2
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from urgp_cli.adapters.base import AdapterResult, BaseAdapter

# Files that indicate a P2 repository structure
_P2_MARKER_FILES = {"content.xml", "content.jar", "compositeContent.xml", "compositeContent.jar"}


class EclipseP2Adapter(BaseAdapter):
    """Adapter for Eclipse P2 repository artifacts.

    Parses P2 repository content to extract:
        - Installable Unit (IU) identifiers and versions
        - Feature vs. plugin classification
        - P2 repository metadata (size, timestamp)
    """

    @property
    def adapter_type(self) -> str:
        return "eclipse_p2"

    def extract_metadata(self, artifact_path: Path) -> AdapterResult:
        """Extract P2 repository metadata from a ZIP artifact.

        The adapter searches for ``content.xml`` (or ``content.jar`` containing
        ``content.xml``) inside the ZIP and parses Installable Unit definitions.

        Args:
            artifact_path: Path to the P2 repository ZIP file.

        Returns:
            AdapterResult with IU metadata, feature/plugin lists, and any errors.
        """
        self._ensure_file_exists(artifact_path)

        errors: list[str] = []
        features: list[dict[str, str]] = []
        plugins: list[dict[str, str]] = []
        all_ius: list[dict[str, str]] = []

        try:
            content_xml = self._find_content_xml(artifact_path)
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            return AdapterResult(
                metadata={"error": str(exc)},
                errors=[f"Failed to read P2 repository: {exc}"],
            )

        if content_xml is None:
            return AdapterResult(
                metadata={},
                errors=["No content.xml or content.jar found in artifact — not a valid P2 repository"],
            )

        try:
            root = ET.fromstring(content_xml)
        except ET.ParseError as exc:
            return AdapterResult(
                metadata={},
                errors=[f"Failed to parse content.xml: {exc}"],
            )

        # Extract repository-level metadata
        repo_size = root.get("size", "0")

        # Parse Installable Units
        for unit in root.iter("unit"):
            iu_id = unit.get("id", "")
            iu_version = unit.get("version", "")

            if not iu_id:
                continue

            iu_entry = {"id": iu_id, "version": iu_version}
            all_ius.append(iu_entry)

            # Classify as feature or plugin
            # Features typically have ".feature.group" or ".feature.jar" suffix
            if ".feature.group" in iu_id or ".feature.jar" in iu_id:
                features.append(iu_entry)
            elif not iu_id.startswith("a.jre") and not iu_id.startswith("config."):
                # Exclude JRE and config IUs — remaining are plugins
                plugins.append(iu_entry)

        # Extract dependency information
        dependencies: list[str] = []
        for required in root.iter("required"):
            req_name = required.get("name", "")
            if req_name and req_name not in dependencies:
                dependencies.append(req_name)

        metadata: dict[str, object] = {
            "p2_repository_size": repo_size,
            "iu_count": len(all_ius),
            "feature_count": len(features),
            "plugin_count": len(plugins),
            "features": features,
            "plugins": plugins,
            "installable_units": all_ius,
        }

        return AdapterResult(
            metadata=metadata,
            dependencies=dependencies,
            errors=errors,
        )

    def validate_artifact(self, artifact_path: Path) -> bool:
        """Validate that the artifact is a valid P2 repository ZIP.

        Checks:
            1. File is a valid ZIP archive
            2. Contains at least one P2 marker file (content.xml/jar or compositeContent.xml/jar)

        Args:
            artifact_path: Path to the artifact file.

        Returns:
            True if the artifact is a valid P2 repository.
        """
        try:
            self._ensure_file_exists(artifact_path)
        except (FileNotFoundError, ValueError):
            return False

        if not zipfile.is_zipfile(str(artifact_path)):
            return False

        try:
            with zipfile.ZipFile(artifact_path, "r") as zf:
                names = set(zf.namelist())
                # Check for any P2 marker file (could be at root or nested)
                for name in names:
                    basename = name.rsplit("/", 1)[-1] if "/" in name else name
                    if basename in _P2_MARKER_FILES:
                        return True
        except zipfile.BadZipFile:
            return False

        return False

    @staticmethod
    def _find_content_xml(artifact_path: Path) -> bytes | None:
        """Locate and read content.xml from within the P2 repository ZIP.

        Handles two common P2 packaging formats:
            1. ``content.xml`` directly in the ZIP root
            2. ``content.jar`` in the ZIP root (containing ``content.xml`` inside)

        Args:
            artifact_path: Path to the P2 repository ZIP.

        Returns:
            The raw bytes of content.xml, or None if not found.
        """
        with zipfile.ZipFile(artifact_path, "r") as zf:
            names = zf.namelist()

            # Strategy 1: Direct content.xml
            for name in names:
                basename = name.rsplit("/", 1)[-1] if "/" in name else name
                if basename == "content.xml":
                    return zf.read(name)

            # Strategy 2: content.jar containing content.xml
            for name in names:
                basename = name.rsplit("/", 1)[-1] if "/" in name else name
                if basename == "content.jar":
                    jar_bytes = zf.read(name)
                    with zipfile.ZipFile(io.BytesIO(jar_bytes), "r") as jar_zf:
                        if "content.xml" in jar_zf.namelist():
                            return jar_zf.read("content.xml")

            # Strategy 3: compositeContent.xml (composite repositories)
            for name in names:
                basename = name.rsplit("/", 1)[-1] if "/" in name else name
                if basename == "compositeContent.xml":
                    return zf.read(name)

        return None
