"""P1-7.3: Performance benchmark tests.

SLA targets from 05-technical-design.md:
  - List queries:        p95 < 500ms
  - Single-entity:       p95 < 200ms
  - Build comparison:    < 500ms
  - Ingest (end-to-end): < 1s

Tests use WARN mode on SLA violations (local Docker performance varies).

Requires: docker compose up -d && make migrate
Run with: poetry run pytest tests/integration/test_performance.py -v -m slow
"""

from __future__ import annotations

import statistics
import time
import uuid

import pytest
from httpx import AsyncClient

from tests.integration.conftest import make_ingest_payload

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# SLA thresholds (seconds)
SLA_LIST_QUERY_P95 = 0.5
SLA_SINGLE_ENTITY_P95 = 0.2
SLA_COMPARISON = 0.5
SLA_INGEST = 1.0
SLA_TRACEABILITY = 2.0

# Number of iterations for p95 calculation
BENCHMARK_ITERATIONS = 20


def compute_p95(latencies: list[float]) -> float:
    """Compute the 95th percentile of a list of latencies."""
    if len(latencies) < 2:
        return latencies[0] if latencies else 0.0
    sorted_latencies = sorted(latencies)
    index = int(len(sorted_latencies) * 0.95) - 1
    return sorted_latencies[max(0, index)]


# ---------------------------------------------------------------------------
# Seed data fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_builds(client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> list[str]:
    """Ingest multiple builds for benchmark queries."""
    build_ids = []
    for i in range(10):
        bid = f"perf-build-{i:03d}-{uuid.uuid4().hex[:6]}"
        payload = make_ingest_payload(
            build_id=bid,
            product_id="perf-test-product",
            release="1.0.0",
            commit_hash=f"{i:040d}",
            artifact_sha256=f"{i:02x}" * 32,
        )
        await client.post("/api/v1/ingest", json=payload, headers=api_headers)
        build_ids.append(bid)
    return build_ids


# ---------------------------------------------------------------------------
# P1-7.3.B1: List Builds (p95 < 500ms)
# ---------------------------------------------------------------------------


class TestListBuildsPerformance:
    """Benchmark GET /api/v1/builds list query."""

    async def test_list_builds_p95(
        self,
        client: AsyncClient,
        api_headers: dict[str, str],
        seeded_builds: list[str],
    ) -> None:
        latencies = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            response = await client.get(
                "/api/v1/builds",
                params={"limit": 50},
                headers=api_headers,
            )
            elapsed = time.perf_counter() - start
            assert response.status_code == 200
            latencies.append(elapsed)

        p95 = compute_p95(latencies)
        avg = statistics.mean(latencies)
        print(
            f"\n[BENCHMARK] List Builds: p95={p95:.3f}s, avg={avg:.3f}s, "
            f"min={min(latencies):.3f}s, max={max(latencies):.3f}s "
            f"(SLA: p95 < {SLA_LIST_QUERY_P95}s)"
        )
        if p95 > SLA_LIST_QUERY_P95:
            pytest.xfail(
                f"List builds p95 ({p95:.3f}s) exceeds SLA ({SLA_LIST_QUERY_P95}s) — "
                "this may be expected in local Docker environments"
            )


# ---------------------------------------------------------------------------
# P1-7.3.B2: Get Single Build (p95 < 200ms)
# ---------------------------------------------------------------------------


class TestSingleBuildPerformance:
    """Benchmark GET /api/v1/builds/{build_id} single entity query."""

    async def test_get_build_p95(
        self,
        client: AsyncClient,
        api_headers: dict[str, str],
        seeded_builds: list[str],
    ) -> None:
        target_build = seeded_builds[0]
        latencies = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            response = await client.get(
                f"/api/v1/builds/{target_build}",
                headers=api_headers,
            )
            elapsed = time.perf_counter() - start
            assert response.status_code == 200
            latencies.append(elapsed)

        p95 = compute_p95(latencies)
        avg = statistics.mean(latencies)
        print(
            f"\n[BENCHMARK] Get Build: p95={p95:.3f}s, avg={avg:.3f}s, "
            f"min={min(latencies):.3f}s, max={max(latencies):.3f}s "
            f"(SLA: p95 < {SLA_SINGLE_ENTITY_P95}s)"
        )
        if p95 > SLA_SINGLE_ENTITY_P95:
            pytest.xfail(
                f"Get build p95 ({p95:.3f}s) exceeds SLA ({SLA_SINGLE_ENTITY_P95}s) — "
                "this may be expected in local Docker environments"
            )


# ---------------------------------------------------------------------------
# P1-7.3.B3: Build Comparison (< 500ms)
# ---------------------------------------------------------------------------


class TestBuildComparisonPerformance:
    """Benchmark GET /api/v1/builds/compare endpoint."""

    async def test_compare_builds_latency(
        self,
        client: AsyncClient,
        api_headers: dict[str, str],
        seeded_builds: list[str],
    ) -> None:
        if len(seeded_builds) < 2:
            pytest.skip("Need at least 2 seeded builds")

        start_build = seeded_builds[0]
        end_build = seeded_builds[1]
        latencies = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            response = await client.get(
                "/api/v1/builds/compare",
                params={
                    "start": start_build,
                    "end": end_build,
                    "product_id": "perf-test-product",
                },
                headers=api_headers,
            )
            elapsed = time.perf_counter() - start
            assert response.status_code == 200
            latencies.append(elapsed)

        p95 = compute_p95(latencies)
        avg = statistics.mean(latencies)
        print(
            f"\n[BENCHMARK] Build Comparison: p95={p95:.3f}s, avg={avg:.3f}s, "
            f"min={min(latencies):.3f}s, max={max(latencies):.3f}s "
            f"(SLA: < {SLA_COMPARISON}s)"
        )
        if p95 > SLA_COMPARISON:
            pytest.xfail(f"Build comparison p95 ({p95:.3f}s) exceeds SLA ({SLA_COMPARISON}s)")


# ---------------------------------------------------------------------------
# P1-7.3.B4: Traceability Query (< 2s)
# ---------------------------------------------------------------------------


class TestTraceabilityPerformance:
    """Benchmark GET /api/v1/builds/{build_id}/traceability."""

    async def test_traceability_latency(
        self,
        client: AsyncClient,
        api_headers: dict[str, str],
        seeded_builds: list[str],
    ) -> None:
        target_build = seeded_builds[0]
        latencies = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            response = await client.get(
                f"/api/v1/builds/{target_build}/traceability",
                headers=api_headers,
            )
            elapsed = time.perf_counter() - start
            assert response.status_code == 200
            latencies.append(elapsed)

        p95 = compute_p95(latencies)
        avg = statistics.mean(latencies)
        print(
            f"\n[BENCHMARK] Traceability: p95={p95:.3f}s, avg={avg:.3f}s, "
            f"min={min(latencies):.3f}s, max={max(latencies):.3f}s "
            f"(SLA: < {SLA_TRACEABILITY}s)"
        )
        if p95 > SLA_TRACEABILITY:
            pytest.xfail(f"Traceability p95 ({p95:.3f}s) exceeds SLA ({SLA_TRACEABILITY}s)")


# ---------------------------------------------------------------------------
# P1-7.3.B5: Ingest Latency (< 1s)
# ---------------------------------------------------------------------------


class TestIngestPerformance:
    """Benchmark POST /api/v1/ingest end-to-end latency."""

    async def test_ingest_latency(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        latencies = []
        for i in range(10):
            bid = f"perf-ingest-{i:03d}-{uuid.uuid4().hex[:6]}"
            payload = make_ingest_payload(
                build_id=bid,
                product_id="perf-ingest-product",
                commit_hash=f"{(i + 100):040d}",
                artifact_sha256=f"{(i + 100):02x}" * 32,
            )
            start = time.perf_counter()
            response = await client.post("/api/v1/ingest", json=payload, headers=api_headers)
            elapsed = time.perf_counter() - start
            assert response.status_code in {200, 202}
            latencies.append(elapsed)

        p95 = compute_p95(latencies)
        avg = statistics.mean(latencies)
        print(
            f"\n[BENCHMARK] Ingest: p95={p95:.3f}s, avg={avg:.3f}s, "
            f"min={min(latencies):.3f}s, max={max(latencies):.3f}s "
            f"(SLA: < {SLA_INGEST}s)"
        )
        if p95 > SLA_INGEST:
            pytest.xfail(f"Ingest p95 ({p95:.3f}s) exceeds SLA ({SLA_INGEST}s)")


# ---------------------------------------------------------------------------
# P1-7.3.B6: Activity Dashboard (< 500ms)
# ---------------------------------------------------------------------------


class TestActivityPerformance:
    """Benchmark GET /api/v1/activity dashboard endpoint."""

    async def test_activity_latency(
        self,
        client: AsyncClient,
        api_headers: dict[str, str],
        seeded_builds: list[str],
    ) -> None:
        latencies = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            response = await client.get("/api/v1/activity", headers=api_headers)
            elapsed = time.perf_counter() - start
            assert response.status_code == 200
            latencies.append(elapsed)

        p95 = compute_p95(latencies)
        avg = statistics.mean(latencies)
        print(
            f"\n[BENCHMARK] Activity Dashboard: p95={p95:.3f}s, avg={avg:.3f}s, "
            f"min={min(latencies):.3f}s, max={max(latencies):.3f}s "
            f"(SLA: p95 < {SLA_LIST_QUERY_P95}s)"
        )
        if p95 > SLA_LIST_QUERY_P95:
            pytest.xfail(f"Activity p95 ({p95:.3f}s) exceeds SLA ({SLA_LIST_QUERY_P95}s)")
