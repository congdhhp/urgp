"""Shared test fixtures and configuration."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def sample_product_data() -> dict[str, Any]:
    """Sample product data for testing."""
    return {
        "external_id": "s32-design-studio",
        "name": "S32 Design Studio",
        "description": "NXP S32 Design Studio IDE",
        "git_config": {
            "provider": "bitbucket",
            "repositories": [
                "bitbucket.org/nxp/s32k3_dev",
                "bitbucket.org/nxp/s32k3_drivers",
            ],
            "credentials": {
                "type": "token",
                "token": "test-token",
            },
        },
        "issue_config": {
            "tracker": "jira",
            "base_url": "https://jira.example.com",
            "project_key": "S32",
            "issue_regex": r"S32-\d+",
            "credentials": {
                "type": "token",
                "token": "test-jira-token",
            },
        },
    }


@pytest.fixture
def sample_build_event() -> dict[str, Any]:
    """Sample build event payload (Data Contract) for testing."""
    return {
        "product_id": "s32-design-studio",
        "release": "3.6.8-RFP",
        "build_type": "nightly",
        "build_id": "260330",
        "cli_version": "0.1.0",
        "commit_hashes": [
            {
                "repository": "bitbucket.org/nxp/s32k3_dev",
                "hash": "abc123def456789012345678901234567890abcd",
                "branch": "main",
            },
        ],
        "artifacts": [
            {
                "name": "s32-ide.zip",
                "type": "eclipse_p2",
                "storage_uri": "https://artifacts.example.com/s32-ide-260330.zip",
                "sha256": "a" * 64,
                "size_bytes": 1024000,
                "metadata": {"features": ["com.nxp.s32.ide"]},
            },
        ],
        "timestamp": "2026-03-30T10:30:00Z",
        "ci_metadata": {
            "ci_system": "Jenkins",
            "pipeline_url": "https://jenkins.example.com/job/s32-ide/260330",
            "triggered_by": "nightly-scheduler",
        },
    }
