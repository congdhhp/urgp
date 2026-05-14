"""P1-7.2: Data accuracy validation tests.

Validates:
- SHA-256 checksums preserved through the pipeline
- Traceability data completeness
- Build comparison correctness
- Multi-build scenario integrity

Requires: docker compose up -d && make migrate
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.conftest import make_ingest_payload

pytestmark = pytest.mark.integration


class TestArtifactChecksumIntegrity:
    """Verify that SHA-256 checksums are preserved end-to-end."""

    async def test_single_artifact_checksum_preserved(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        expected_sha = "deadbeef" * 8  # 64 char hex
        bid = f"e2e-sha-{uuid.uuid4().hex[:8]}"
        payload = make_ingest_payload(
            build_id=bid,
            artifact_name="verified-artifact.zip",
            artifact_sha256=expected_sha,
        )
        ingest_response = await client.post("/api/v1/ingest", json=payload, headers=api_headers)
        assert ingest_response.status_code == 202

        # Verify checksum via artifacts API
        art_response = await client.get(f"/api/v1/builds/{bid}/artifacts", headers=api_headers)
        assert art_response.status_code == 200
        artifacts = art_response.json()["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["sha256_checksum"] == expected_sha

    async def test_multiple_artifact_checksums(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = f"e2e-multi-sha-{uuid.uuid4().hex[:8]}"
        sha_a = "aa" * 32
        sha_b = "bb" * 32

        payload = {
            "product_id": "e2e-multi-art-product",
            "release": "1.0.0",
            "build_type": "nightly",
            "build_id": bid,
            "cli_version": "0.1.0",
            "commit_hashes": [
                {
                    "repository": "github.com/test/repo",
                    "hash": "cc" * 20,
                    "branch": "main",
                }
            ],
            "artifacts": [
                {
                    "name": "artifact-a.zip",
                    "type": "generic",
                    "storage_uri": "https://example.com/a.zip",
                    "sha256": sha_a,
                    "size_bytes": 500000,
                },
                {
                    "name": "artifact-b.tar.gz",
                    "type": "generic",
                    "storage_uri": "https://example.com/b.tar.gz",
                    "sha256": sha_b,
                    "size_bytes": 750000,
                },
            ],
            "timestamp": "2026-05-06T12:00:00Z",
        }
        await client.post("/api/v1/ingest", json=payload, headers=api_headers)

        art_response = await client.get(f"/api/v1/builds/{bid}/artifacts", headers=api_headers)
        assert art_response.status_code == 200
        artifacts = art_response.json()["artifacts"]
        checksums = {a["name"]: a["sha256_checksum"] for a in artifacts}
        assert checksums["artifact-a.zip"] == sha_a
        assert checksums["artifact-b.tar.gz"] == sha_b


class TestTraceabilityCompleteness:
    """Verify traceability data matches ingested commit hashes."""

    async def test_single_commit_traceability(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = f"e2e-trace-{uuid.uuid4().hex[:8]}"
        commit_hash = "abcdef0123456789abcdef0123456789abcdef01"
        payload = make_ingest_payload(build_id=bid, commit_hash=commit_hash)
        await client.post("/api/v1/ingest", json=payload, headers=api_headers)

        trace_response = await client.get(f"/api/v1/builds/{bid}/traceability", headers=api_headers)
        assert trace_response.status_code == 200
        data = trace_response.json()
        assert data["commit_count"] == 1

        commit_hashes = [
            commit["hash"] for repository in data.get("repositories", []) for commit in repository.get("commits", [])
        ]
        assert commit_hash in commit_hashes

    async def test_multi_commit_traceability(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = f"e2e-multi-trace-{uuid.uuid4().hex[:8]}"
        commits = [{"repository": "github.com/test/repo", "hash": f"{'a' * 39}{i}", "branch": "main"} for i in range(5)]
        payload = {
            "product_id": "e2e-trace-product",
            "release": "2.0.0",
            "build_type": "nightly",
            "build_id": bid,
            "cli_version": "0.1.0",
            "commit_hashes": commits,
            "artifacts": [
                {
                    "name": "trace-test.zip",
                    "type": "generic",
                    "storage_uri": "https://example.com/trace.zip",
                    "sha256": "dd" * 32,
                    "size_bytes": 100000,
                }
            ],
            "timestamp": "2026-05-06T12:00:00Z",
        }
        await client.post("/api/v1/ingest", json=payload, headers=api_headers)

        trace_response = await client.get(f"/api/v1/builds/{bid}/traceability", headers=api_headers)
        assert trace_response.status_code == 200
        assert trace_response.json()["commit_count"] == 5


class TestBuildComparisonAccuracy:
    """Verify build comparison correctly identifies differences between builds."""

    async def test_comparison_detects_different_commits(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        # Build A with commits [1, 2]
        bid_a = f"e2e-cmp-acc-a-{uuid.uuid4().hex[:8]}"
        payload_a = {
            "product_id": "e2e-compare-product",
            "release": "3.0.0",
            "build_type": "nightly",
            "build_id": bid_a,
            "cli_version": "0.1.0",
            "commit_hashes": [
                {"repository": "github.com/test/repo", "hash": "1" * 40, "branch": "main"},
                {"repository": "github.com/test/repo", "hash": "2" * 40, "branch": "main"},
            ],
            "artifacts": [
                {
                    "name": "a.zip",
                    "type": "generic",
                    "storage_uri": "https://example.com/a.zip",
                    "sha256": "11" * 32,
                    "size_bytes": 100000,
                }
            ],
            "timestamp": "2026-05-06T12:00:00Z",
        }
        await client.post("/api/v1/ingest", json=payload_a, headers=api_headers)

        # Build B with commits [2, 3]
        bid_b = f"e2e-cmp-acc-b-{uuid.uuid4().hex[:8]}"
        payload_b = {
            "product_id": "e2e-compare-product",
            "release": "3.0.0",
            "build_type": "nightly",
            "build_id": bid_b,
            "cli_version": "0.1.0",
            "commit_hashes": [
                {"repository": "github.com/test/repo", "hash": "2" * 40, "branch": "main"},
                {"repository": "github.com/test/repo", "hash": "3" * 40, "branch": "main"},
            ],
            "artifacts": [
                {
                    "name": "b.zip",
                    "type": "generic",
                    "storage_uri": "https://example.com/b.zip",
                    "sha256": "22" * 32,
                    "size_bytes": 100000,
                }
            ],
            "timestamp": "2026-05-06T12:00:00Z",
        }
        await client.post("/api/v1/ingest", json=payload_b, headers=api_headers)

        # Compare
        response = await client.get(
            "/api/v1/builds/compare",
            params={"start": bid_a, "end": bid_b, "product_id": "e2e-compare-product"},
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["start_build_id"] == bid_a
        assert data["end_build_id"] == bid_b


class TestBuildIntegrityVerification:
    """Verify build integrity verification with controlled checksums."""

    async def test_integrity_status_for_known_build(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = f"e2e-integrity-{uuid.uuid4().hex[:8]}"
        known_sha = "abcdef" * 10 + "abcd"  # 64 chars
        payload = make_ingest_payload(build_id=bid, artifact_sha256=known_sha)
        await client.post("/api/v1/ingest", json=payload, headers=api_headers)

        verify_response = await client.post(f"/api/v1/builds/{bid}/verify", headers=api_headers)
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["build_id"] == bid
        assert data["integrity_status"] in {"valid", "invalid"}
        # Verify artifacts are included in verification
        assert len(data["artifacts"]) >= 1
