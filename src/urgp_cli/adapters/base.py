"""Base adapter interface for URGP CLI.

Defines the abstract base class for all artifact adapters and the
standardized result type. Adapters extract technology-specific metadata
from build outputs and translate them into the URGP Data Contract format.

Reference:
    - docs/05-technical-design.md § Adapter Interface
    - docs/07-implementation-plan.md § P1-2.3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AdapterResult:
    """Result of adapter metadata extraction.

    Attributes:
        metadata: Technology-specific metadata dict (stored as JSONB in DB).
        dependencies: List of detected dependencies (e.g., feature IDs).
        errors: Non-fatal extraction warnings/issues encountered.
    """

    metadata: dict[str, object] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseAdapter(ABC):
    """Abstract base class for all URGP artifact adapters.

    Each adapter is responsible for extracting technology-specific metadata
    from a build artifact and validating its structural integrity.

    Phase 1 adapters: ``GenericAdapter``, ``EclipseP2Adapter``
    Phase 2 adapters: ``OciImageAdapter``, ``MavenJarAdapter``, ``NpmTarballAdapter``
    """

    @abstractmethod
    def extract_metadata(self, artifact_path: Path) -> AdapterResult:
        """Extract technology-specific metadata from a build artifact.

        Args:
            artifact_path: Path to the artifact file.

        Returns:
            AdapterResult with extracted metadata, dependencies, and any errors.

        Raises:
            FileNotFoundError: If the artifact path does not exist.
            ValueError: If the artifact is not a valid file for this adapter.
        """
        ...

    @abstractmethod
    def validate_artifact(self, artifact_path: Path) -> bool:
        """Validate artifact integrity for this adapter type.

        Checks that the file is structurally valid for the technology type
        (e.g., ZIP is not corrupted, P2 repo has content.xml).

        Args:
            artifact_path: Path to the artifact file.

        Returns:
            True if the artifact is valid for this adapter type.
        """
        ...

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Return the adapter type identifier (e.g., 'generic', 'eclipse_p2')."""
        ...

    def _ensure_file_exists(self, artifact_path: Path) -> None:
        """Validate that the artifact file exists and is readable.

        Args:
            artifact_path: Path to check.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the path is not a file.
        """
        if not artifact_path.exists():
            msg = f"Artifact not found: {artifact_path}"
            raise FileNotFoundError(msg)
        if not artifact_path.is_file():
            msg = f"Artifact path is not a file: {artifact_path}"
            raise ValueError(msg)
