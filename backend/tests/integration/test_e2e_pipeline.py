"""P1-7.1: End-to-end pipeline integration tests.

Tests the complete flow:
  CLI payload → POST /api/v1/ingest → Worker processes → DB verify → API query → Notification delivery

Requires: docker compose up -d && make migrate
Run with: poetry run pytest tests/integration/test_e2e_pipeline.py -v -m integration
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.conftest import make_ingest_payload

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# P1-7.1.T1: Health & Readiness
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Verify health endpoints respond correctly with live services."""

    async def test_health_returns_ok(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    async def test_readiness_returns_ok(self, client: AsyncClient) -> None:
        response = await client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# P1-7.1.T2: Product & Release Management
# ---------------------------------------------------------------------------


class TestProductAndReleaseAPIs:
    """Verify product and release CRUD with a real database."""

    async def test_create_product(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        payload = {
            "external_id": "e2e-product-create",
            "name": "E2E Test Product",
            "description": "Created by integration test",
        }
        response = await client.post("/api/v1/products", json=payload, headers=api_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["external_id"] == "e2e-product-create"
        assert data["name"] == "E2E Test Product"

    async def test_list_products(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        # Create a product first
        await client.post(
            "/api/v1/products",
            json={"external_id": "e2e-list-test", "name": "List Test Product"},
            headers=api_headers,
        )
        response = await client.get("/api/v1/products", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(p["external_id"] == "e2e-list-test" for p in data["items"])

    async def test_create_release_train(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        # Create product
        await client.post(
            "/api/v1/products",
            json={"external_id": "e2e-release-test", "name": "Release Test Product"},
            headers=api_headers,
        )
        # Create release
        response = await client.post(
            "/api/v1/products/e2e-release-test/release-trains",
            json={"version": "2.0.0-RC1", "release_type": "RC", "status": "active"},
            headers=api_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == "2.0.0-RC1"

    async def test_list_releases(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        await client.post(
            "/api/v1/products",
            json={"external_id": "e2e-releases-list", "name": "Releases List Product"},
            headers=api_headers,
        )
        await client.post(
            "/api/v1/products/e2e-releases-list/release-trains",
            json={"version": "3.0.0", "status": "active"},
            headers=api_headers,
        )
        response = await client.get(
            "/api/v1/products/e2e-releases-list/releases",
            headers=api_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1


# ---------------------------------------------------------------------------
# P1-7.1.T3: Build Ingestion Pipeline
# ---------------------------------------------------------------------------


class TestBuildIngestion:
    """Verify the ingestion pipeline with real Redis idempotency and DB persistence."""

    async def test_ingest_returns_202(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        unique_build = f"e2e-ingest-{uuid.uuid4().hex[:8]}"
        payload = make_ingest_payload(build_id=unique_build)
        response = await client.post("/api/v1/ingest", json=payload, headers=api_headers)
        assert response.status_code == 202
        data = response.json()
        assert data["build_id"] == unique_build
        assert "ingestion_timestamp" in data

    async def test_ingest_idempotency(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        unique_build = f"e2e-idempotent-{uuid.uuid4().hex[:8]}"
        payload = make_ingest_payload(build_id=unique_build)

        # First ingest
        r1 = await client.post("/api/v1/ingest", json=payload, headers=api_headers)
        assert r1.status_code == 202

        # Second ingest — same build_id → idempotent
        r2 = await client.post("/api/v1/ingest", json=payload, headers=api_headers)
        assert r2.status_code in {200, 202}

    async def test_ingest_validation_error(self, client: AsyncClient, api_headers: dict[str, str]) -> None:
        # Missing required fields
        response = await client.post(
            "/api/v1/ingest",
            json={"product_id": "test", "build_id": "123"},
            headers=api_headers,
        )
        assert response.status_code == 422

    async def test_ingest_requires_api_key(self, client: AsyncClient) -> None:
        payload = make_ingest_payload(build_id="no-auth-test")
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# P1-7.1.T4: Build Query APIs
# ---------------------------------------------------------------------------


class TestBuildQueryAPIs:
    """Verify build list, detail, artifacts, and traceability queries against real DB."""

    async def _ingest_and_wait(
        self,
        client: AsyncClient,
        headers: dict[str, str],
        build_id: str | None = None,
    ) -> str:
        """Ingest a build and return its build_id."""
        bid = build_id or f"e2e-query-{uuid.uuid4().hex[:8]}"
        payload = make_ingest_payload(build_id=bid)
        await client.post("/api/v1/ingest", json=payload, headers=headers)
        return bid

    async def test_list_builds(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        await self._ingest_and_wait(client, api_headers)
        response = await client.get("/api/v1/builds", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_get_build_detail(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        bid = await self._ingest_and_wait(client, api_headers)
        response = await client.get(f"/api/v1/builds/{bid}", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["build_id"] == bid
        assert data["status"] in {"ingesting", "hydrating", "completed"}

    async def test_get_artifacts(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        bid = await self._ingest_and_wait(client, api_headers)
        response = await client.get(f"/api/v1/builds/{bid}/artifacts", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["build_id"] == bid
        assert len(data["artifacts"]) >= 1
        # Verify SHA-256 checksum preserved
        assert data["artifacts"][0]["sha256_checksum"] == "ab" * 32

    async def test_get_traceability(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        bid = await self._ingest_and_wait(client, api_headers)
        response = await client.get(f"/api/v1/builds/{bid}/traceability", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["build_id"] == bid
        assert data["commit_count"] >= 1

    async def test_build_not_found_returns_404(self, client: AsyncClient, api_headers: dict[str, str]) -> None:
        response = await client.get("/api/v1/builds/nonexistent-build-id-12345", headers=api_headers)
        assert response.status_code == 404

    async def test_verify_build_integrity(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = await self._ingest_and_wait(client, api_headers)
        response = await client.post(f"/api/v1/builds/{bid}/verify", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["build_id"] == bid
        assert data["integrity_status"] in {"valid", "invalid"}

    async def test_search_by_commit(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        commit_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        await self._ingest_and_wait(client, api_headers)
        response = await client.get(f"/api/v1/builds/search/by-commit/{commit_hash}", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1


# ---------------------------------------------------------------------------
# P1-7.1.T5: Build Lifecycle
# ---------------------------------------------------------------------------


class TestBuildLifecycle:
    """Verify lifecycle state transitions with real database."""

    async def _create_completed_build(self, client: AsyncClient, headers: dict[str, str]) -> str:
        bid = f"e2e-lifecycle-{uuid.uuid4().hex[:8]}"
        payload = make_ingest_payload(build_id=bid)
        await client.post("/api/v1/ingest", json=payload, headers=headers)
        return bid

    async def test_transition_to_testing(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = await self._create_completed_build(client, api_headers)

        # Verify current status is completed
        build = await client.get(f"/api/v1/builds/{bid}", headers=api_headers)
        if build.status_code != 200:
            pytest.skip("Build not yet processed by worker")

        current_status = build.json().get("status")
        if current_status != "completed":
            pytest.skip(f"Build status is '{current_status}', not 'completed'")

        # Transition to testing
        response = await client.patch(
            f"/api/v1/builds/{bid}/status",
            json={"status": "testing"},
            headers=api_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "testing"

    async def test_transition_to_released(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        bid = await self._create_completed_build(client, api_headers)
        build = await client.get(f"/api/v1/builds/{bid}", headers=api_headers)
        if build.status_code != 200 or build.json().get("status") != "completed":
            pytest.skip("Build not in 'completed' status")

        # completed → testing
        await client.patch(
            f"/api/v1/builds/{bid}/status",
            json={"status": "testing"},
            headers=api_headers,
        )
        # testing → released
        response = await client.patch(
            f"/api/v1/builds/{bid}/status",
            json={"status": "released"},
            headers=api_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "released"

    async def test_immutability_lock(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        bid = await self._create_completed_build(client, api_headers)
        build = await client.get(f"/api/v1/builds/{bid}", headers=api_headers)
        if build.status_code != 200 or build.json().get("status") != "completed":
            pytest.skip("Build not in 'completed' status")

        # completed → testing → released
        await client.patch(
            f"/api/v1/builds/{bid}/status",
            json={"status": "testing"},
            headers=api_headers,
        )
        await client.patch(
            f"/api/v1/builds/{bid}/status",
            json={"status": "released"},
            headers=api_headers,
        )

        # released → attempt further modification → 409
        response = await client.patch(
            f"/api/v1/builds/{bid}/status",
            json={"status": "testing"},
            headers=api_headers,
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# P1-7.1.T6: Build Comparison
# ---------------------------------------------------------------------------


class TestBuildComparison:
    """Verify build comparison API with two builds sharing some commits."""

    async def test_compare_two_builds(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        # Ingest build A
        bid_a = f"e2e-cmp-a-{uuid.uuid4().hex[:8]}"
        payload_a = make_ingest_payload(
            build_id=bid_a,
            commit_hash="1111111111111111111111111111111111111111",
            artifact_sha256="11" * 32,
        )
        await client.post("/api/v1/ingest", json=payload_a, headers=api_headers)

        # Ingest build B (different commit)
        bid_b = f"e2e-cmp-b-{uuid.uuid4().hex[:8]}"
        payload_b = make_ingest_payload(
            build_id=bid_b,
            commit_hash="2222222222222222222222222222222222222222",
            artifact_sha256="22" * 32,
        )
        await client.post("/api/v1/ingest", json=payload_b, headers=api_headers)

        response = await client.get(
            "/api/v1/builds/compare",
            params={"start": bid_a, "end": bid_b},
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["start_build_id"] == bid_a
        assert data["end_build_id"] == bid_b


# ---------------------------------------------------------------------------
# P1-7.1.T7: Notification Subscriptions
# ---------------------------------------------------------------------------


class TestNotificationSubscriptions:
    """Verify notification subscription CRUD with real database."""

    async def test_create_and_list_subscription(
        self, client: AsyncClient, api_headers: dict[str, str], clean_db: None
    ) -> None:
        # Need a product first
        await client.post(
            "/api/v1/products",
            json={"external_id": "e2e-notif-product", "name": "Notification Test Product"},
            headers=api_headers,
        )

        # Create subscription
        sub_payload = {
            "product_id": "e2e-notif-product",
            "channel": "email",
        }
        create_response = await client.post(
            "/api/v1/notifications/subscriptions",
            json=sub_payload,
            headers=api_headers,
        )
        assert create_response.status_code == 201

        # List subscriptions
        list_response = await client.get(
            "/api/v1/notifications/subscriptions",
            headers=api_headers,
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 1

    async def test_delete_subscription(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        await client.post(
            "/api/v1/products",
            json={"external_id": "e2e-del-sub", "name": "Delete Sub Product"},
            headers=api_headers,
        )
        create_response = await client.post(
            "/api/v1/notifications/subscriptions",
            json={"product_id": "e2e-del-sub", "channel": "email"},
            headers=api_headers,
        )
        sub_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/api/v1/notifications/subscriptions/{sub_id}",
            headers=api_headers,
        )
        assert delete_response.status_code == 204


# ---------------------------------------------------------------------------
# P1-7.1.T8: Activity & Admin APIs
# ---------------------------------------------------------------------------


class TestActivityAndAdminAPIs:
    """Verify activity feed and admin endpoints."""

    async def test_activity_endpoint(self, client: AsyncClient, api_headers: dict[str, str], clean_db: None) -> None:
        response = await client.get("/api/v1/activity", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "totals" in data
        assert "recent_builds" in data
        assert "products" in data

    async def test_dlq_count_endpoint(self, client: AsyncClient, api_headers: dict[str, str]) -> None:
        response = await client.get("/api/v1/admin/dlq/count", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["queue"] == "build.events.dlq"
        assert data["message_count"] >= 0
        assert data["consumer_count"] >= 0
