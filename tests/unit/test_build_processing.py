"""Unit tests for build processing helpers."""

from __future__ import annotations

from urgp.services.build_processing import _build_default_product_name, _infer_release_type


class TestBuildProcessingHelpers:
    """Identity and release normalization should stay deterministic."""

    def test_build_default_product_name_normalizes_common_keys(self) -> None:
        assert _build_default_product_name("s32-design-studio") == "S32 Design Studio"
        assert _build_default_product_name("S32_IDE") == "S32 IDE"

    def test_infer_release_type_from_semantic_suffix(self) -> None:
        assert _infer_release_type("3.6.8-RFP") == "RFP"
        assert _infer_release_type("2026.04") is None
