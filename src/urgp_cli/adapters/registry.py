"""Adapter registry — discovery and instantiation of artifact adapters.

Reference:
    - docs/07-implementation-plan.md § P1-2.3
"""

from __future__ import annotations

from urgp_cli.adapters.base import BaseAdapter


def get_adapter(adapter_type: str) -> BaseAdapter:
    """Get an adapter instance by type identifier.

    Args:
        adapter_type: The adapter type string (e.g., ``"generic"``, ``"eclipse_p2"``).

    Returns:
        An instantiated adapter for the given type.

    Raises:
        ValueError: If the adapter type is not registered.
    """
    registry = _build_registry()
    normalized = adapter_type.lower().strip()

    if normalized not in registry:
        available = ", ".join(sorted(registry.keys()))
        msg = f"Unknown adapter type '{adapter_type}'. Available adapters: {available}"
        raise ValueError(msg)

    return registry[normalized]()


def list_adapters() -> list[str]:
    """Return a sorted list of available adapter type identifiers."""
    return sorted(_build_registry().keys())


def _build_registry() -> dict[str, type[BaseAdapter]]:
    """Build the adapter type → class mapping.

    Imports are deferred to avoid circular imports and to keep the registry
    lightweight until an adapter is actually requested.
    """
    from urgp_cli.adapters.eclipse_p2 import EclipseP2Adapter
    from urgp_cli.adapters.generic import GenericAdapter

    return {
        "generic": GenericAdapter,
        "eclipse_p2": EclipseP2Adapter,
    }
