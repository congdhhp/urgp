"""Unit tests for build processing helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from urgp.integrations.git.github import GitHubProvider
from urgp.integrations.issues.jira import JiraTracker
from urgp.services.build_processing import BuildEventProcessor, _build_default_product_name, _infer_release_type
from urgp.services.cache import CacheService


class TestBuildProcessingHelpers:
    """Identity and release normalization should stay deterministic."""

    def test_build_default_product_name_normalizes_common_keys(self) -> None:
        assert _build_default_product_name("s32-design-studio") == "S32 Design Studio"
        assert _build_default_product_name("S32_IDE") == "S32 IDE"

    def test_infer_release_type_from_semantic_suffix(self) -> None:
        assert _infer_release_type("3.6.8-RFP") == "RFP"
        assert _infer_release_type("2026.04") is None


class TestBuildEventProcessorProviderResolution:
    def test_resolve_git_provider_from_product_config(self) -> None:
        settings = MagicMock()
        settings.default_git_provider = "github"
        settings.default_issue_tracker = "jira"
        processor = BuildEventProcessor(
            lambda: MagicMock(),
            MagicMock(),
            settings,
            cache=CacheService(None),
        )

        provider = processor._resolve_git_provider(
            {
                "provider": "github",
                "credentials": {"authentication_token": "test-token"},
                "base_url": "https://github.internal.example/api/v3",
            }
        )

        assert isinstance(provider, GitHubProvider)
        assert provider._api_base_url == "https://github.internal.example/api/v3"

    def test_resolve_issue_tracker_from_product_config(self) -> None:
        settings = MagicMock()
        settings.default_git_provider = "github"
        settings.default_issue_tracker = "jira"
        processor = BuildEventProcessor(
            lambda: MagicMock(),
            MagicMock(),
            settings,
            cache=CacheService(None),
        )

        tracker = processor._resolve_issue_tracker(
            {
                "tracker": "jira",
                "base_url": "https://jira.internal.example",
                "credentials": {"authentication_token": "test-token"},
            }
        )

        assert isinstance(tracker, JiraTracker)
