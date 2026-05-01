"""Unit tests for platform query and management APIs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.unit.fakes import FakeRedis
from urgp.main import create_app
from urgp.models.enums import (
    ArtifactType,
    BuildStatus,
    BuildType,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from urgp.schemas.platform import (
    ActivityResponse,
    ActivityTotalsResponse,
    BuildDetailResponse,
    BuildStatusTransitionRequest,
    BuildSummaryResponse,
    BuildVerificationArtifactResponse,
    BuildVerificationResponse,
    NotificationHistoryItemResponse,
    NotificationHistoryResponse,
    ProductListResponse,
    ProductSummaryResponse,
    SubscriptionCreateRequest,
    SubscriptionListResponse,
    SubscriptionResponse,
)
from urgp.services.lifecycle import InvalidBuildTransitionError
from urgp.services.notification_processing import SubscriptionNotFoundError
from urgp.services.platform_queries import AmbiguousBuildReferenceError, BuildNotFoundError, ProductNotFoundError

_TEST_API_KEY = "test-api-key-for-platform-tests"


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.api_keys = [_TEST_API_KEY]
    settings.rate_limit_read = 100
    settings.rate_limit_write = 20
    settings.idempotency_ttl_seconds = 86400
    settings.idempotency_pending_ttl_seconds = 120
    settings.validation_dlq_max_body_bytes = 65536
    settings.rabbitmq_url = "amqp://test:test@localhost:5672/"
    settings.portal_base_url = "http://localhost:8000/portal"
    settings.notification_max_retries = 3
    settings.notification_retry_backoff_seconds = 1.0
    settings.notification_wait_timeout_seconds = 30.0
    settings.notification_poll_interval_seconds = 0.5
    settings.smtp_from = "urgp@example.com"
    settings.smtp_host = "localhost"
    settings.smtp_port = 1025
    settings.smtp_username = ""
    settings.smtp_password = ""
    settings.default_issue_tracker = "jira"
    settings.default_issue_regex = r"\b[A-Z][A-Z0-9]+-\d+\b"
    return settings


def _build_summary() -> BuildSummaryResponse:
    return BuildSummaryResponse(
        id=uuid.uuid4(),
        build_id="260330",
        product_id="S32_IDE",
        product_name="S32 Design Studio",
        release="3.6.8-RFP",
        build_type=BuildType.NIGHTLY,
        status=BuildStatus.COMPLETED,
        traceability_incomplete=False,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
        artifact_count=1,
        commit_count=2,
        pull_request_count=1,
        issue_count=1,
        notification_count=0,
    )


def _build_detail() -> BuildDetailResponse:
    summary = _build_summary()
    data = summary.model_dump()
    data["cli_version"] = "1.0.0"
    data["signature"] = "sig"
    return BuildDetailResponse(**data, ci_metadata=None)


def _subscription_response() -> SubscriptionResponse:
    return SubscriptionResponse(
        id=uuid.uuid4(),
        user_id="qa@example.com",
        product_id="S32_IDE",
        product_name="S32 Design Studio",
        release="3.6.8-RFP",
        channel=NotificationChannel.EMAIL,
        webhook_url=None,
        active=True,
        created_at=datetime.now(tz=UTC),
    )


def _notification_history_item() -> NotificationHistoryItemResponse:
    return NotificationHistoryItemResponse(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        manifest_id=uuid.uuid4(),
        build_id="260330",
        product_id="S32_IDE",
        product_name="S32 Design Studio",
        release="3.6.8-RFP",
        event_type=NotificationEventType.BUILD_COMPLETED,
        channel=NotificationChannel.EMAIL,
        recipient="qa@example.com",
        status=NotificationDeliveryStatus.SENT,
        attempt_count=1,
        last_attempt_at=datetime.now(tz=UTC),
        sent_at=datetime.now(tz=UTC),
        last_error=None,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def platform_client() -> TestClient:
    settings = _settings()
    with patch("urgp.config.get_settings", return_value=settings):
        app = create_app()
        app.state.redis = FakeRedis()
        app.state.publisher = None
        app.state.session_factory = object()
        yield TestClient(app, raise_server_exceptions=False)


class TestProductsApi:
    def test_list_products_uses_platform_service(self, platform_client: TestClient) -> None:
        response_model = ProductListResponse(
            items=[ProductSummaryResponse(external_id="S32_IDE", name="S32 Design Studio")],
            total=1,
        )

        with patch("urgp.api.products.PlatformQueryService") as service_cls:
            service_cls.return_value.list_products = AsyncMock(return_value=response_model)
            response = platform_client.get("/api/v1/products", headers={"X-API-Key": _TEST_API_KEY})

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_releases_returns_404_for_unknown_product(self, platform_client: TestClient) -> None:
        with patch("urgp.api.products.PlatformQueryService") as service_cls:
            service_cls.return_value.list_releases = AsyncMock(side_effect=ProductNotFoundError("missing"))
            response = platform_client.get("/api/v1/products/missing/releases", headers={"X-API-Key": _TEST_API_KEY})

        assert response.status_code == 404
        assert response.json()["detail"] == "missing"

    def test_release_trains_alias_matches_documented_route(self, platform_client: TestClient) -> None:
        with patch("urgp.api.products.PlatformQueryService") as service_cls:
            service_cls.return_value.list_releases = AsyncMock(
                return_value={"product_id": "S32_IDE", "product_name": "S32 Design Studio", "items": [], "total": 0}
            )
            response = platform_client.get(
                "/api/v1/products/S32_IDE/release-trains",
                headers={"X-API-Key": _TEST_API_KEY},
            )

        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestBuildsApi:
    def test_get_build_returns_detail_payload(self, platform_client: TestClient) -> None:
        with patch("urgp.api.builds.PlatformQueryService") as service_cls:
            service_cls.return_value.get_build = AsyncMock(return_value=_build_detail())
            response = platform_client.get(
                "/api/v1/builds/260330",
                headers={"X-API-Key": _TEST_API_KEY},
                params={"product_id": "S32_IDE"},
            )

        assert response.status_code == 200
        assert response.json()["build_id"] == "260330"

    def test_transition_build_status_maps_conflict(self, platform_client: TestClient) -> None:
        with patch("urgp.api.builds.PlatformQueryService") as service_cls:
            service_cls.return_value.transition_build_status = AsyncMock(
                side_effect=InvalidBuildTransitionError("invalid transition")
            )
            response = platform_client.patch(
                "/api/v1/builds/260330/status",
                headers={"X-API-Key": _TEST_API_KEY},
                params={"product_id": "S32_IDE"},
                json=BuildStatusTransitionRequest(status=BuildStatus.RELEASED).model_dump(mode="json"),
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "invalid transition"

    def test_verify_build_returns_integrity_payload(self, platform_client: TestClient) -> None:
        verification = BuildVerificationResponse(
            build_id="260330",
            product_id="S32_IDE",
            integrity_status="valid",
            traceability_incomplete=False,
            artifacts=[
                BuildVerificationArtifactResponse(
                    name="s32-ide.zip",
                    type=ArtifactType.ECLIPSE_P2,
                    sha256="a" * 64,
                    integrity_status="valid",
                    detail="ok",
                )
            ],
            verification_timestamp=datetime.now(tz=UTC),
        )

        with patch("urgp.api.builds.PlatformQueryService") as service_cls:
            service_cls.return_value.verify_build_integrity = AsyncMock(return_value=verification)
            response = platform_client.post(
                "/api/v1/builds/260330/verify",
                headers={"X-API-Key": _TEST_API_KEY},
                params={"product_id": "S32_IDE"},
            )

        assert response.status_code == 200
        assert response.json()["integrity_status"] == "valid"

    def test_lookup_conflict_returns_409(self, platform_client: TestClient) -> None:
        with patch("urgp.api.builds.PlatformQueryService") as service_cls:
            service_cls.return_value.get_build = AsyncMock(side_effect=AmbiguousBuildReferenceError("ambiguous"))
            response = platform_client.get("/api/v1/builds/260330", headers={"X-API-Key": _TEST_API_KEY})

        assert response.status_code == 409

    def test_missing_build_returns_404(self, platform_client: TestClient) -> None:
        with patch("urgp.api.builds.PlatformQueryService") as service_cls:
            service_cls.return_value.get_build = AsyncMock(side_effect=BuildNotFoundError("missing"))
            response = platform_client.get("/api/v1/builds/260330", headers={"X-API-Key": _TEST_API_KEY})

        assert response.status_code == 404


class TestActivityAndNotificationsApi:
    def test_activity_endpoint_returns_dashboard(self, platform_client: TestClient) -> None:
        payload = ActivityResponse(
            generated_at=datetime.now(tz=UTC),
            totals=ActivityTotalsResponse(
                products=1,
                releases=2,
                builds=3,
                released_builds=1,
                incomplete_builds=0,
            ),
            recent_builds=[_build_summary()],
            products=[ProductSummaryResponse(external_id="S32_IDE", name="S32 Design Studio")],
        )

        with patch("urgp.api.activity.PlatformQueryService") as service_cls:
            service_cls.return_value.get_activity = AsyncMock(return_value=payload)
            response = platform_client.get("/api/v1/activity", headers={"X-API-Key": _TEST_API_KEY})

        assert response.status_code == 200
        assert response.json()["totals"]["builds"] == 3

    def test_subscription_crud_contracts(self, platform_client: TestClient) -> None:
        subscription = _subscription_response()
        history_item = _notification_history_item()

        with (
            patch("urgp.api.notifications.SubscriptionService") as subscription_service_cls,
            patch("urgp.api.notifications.NotificationHistoryService") as history_service_cls,
        ):
            subscription_service = subscription_service_cls.return_value
            history_service = history_service_cls.return_value
            subscription_service.list_subscriptions = AsyncMock(
                return_value=SubscriptionListResponse(items=[subscription], total=1)
            )
            subscription_service.create_subscription = AsyncMock(return_value=subscription)
            subscription_service.delete_subscription = AsyncMock(return_value=None)
            history_service.list_history = AsyncMock(
                return_value=NotificationHistoryResponse(items=[history_item], total=1)
            )

            list_response = platform_client.get(
                "/api/v1/notifications/subscriptions",
                headers={"X-API-Key": _TEST_API_KEY, "X-User-Id": "qa@example.com"},
            )
            history_response = platform_client.get(
                "/api/v1/notifications/history",
                headers={"X-API-Key": _TEST_API_KEY, "X-User-Id": "qa@example.com"},
                params={"status": "sent", "limit": 10},
            )
            create_response = platform_client.post(
                "/api/v1/notifications/subscriptions",
                headers={"X-API-Key": _TEST_API_KEY, "X-User-Id": "qa@example.com"},
                json=SubscriptionCreateRequest(
                    product_id="S32_IDE",
                    release="3.6.8-RFP",
                    channel=NotificationChannel.EMAIL,
                ).model_dump(mode="json"),
            )
            delete_response = platform_client.delete(
                f"/api/v1/notifications/subscriptions/{subscription.id}",
                headers={"X-API-Key": _TEST_API_KEY, "X-User-Id": "qa@example.com"},
            )

        assert list_response.status_code == 200
        assert history_response.status_code == 200
        assert create_response.status_code == 201
        assert delete_response.status_code == 204

    def test_delete_subscription_returns_404_when_missing(self, platform_client: TestClient) -> None:
        with patch("urgp.api.notifications.SubscriptionService") as service_cls:
            service_cls.return_value.delete_subscription = AsyncMock(side_effect=SubscriptionNotFoundError("missing"))
            response = platform_client.delete(
                f"/api/v1/notifications/subscriptions/{uuid.uuid4()}",
                headers={"X-API-Key": _TEST_API_KEY, "X-User-Id": "qa@example.com"},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "missing"

    def test_history_rejects_invalid_status_filter(self, platform_client: TestClient) -> None:
        with patch("urgp.api.notifications.NotificationHistoryService") as service_cls:
            service_cls.return_value.list_history = AsyncMock(side_effect=ValueError("bad status"))
            response = platform_client.get(
                "/api/v1/notifications/history",
                headers={"X-API-Key": _TEST_API_KEY, "X-User-Id": "qa@example.com"},
                params={"status": "bad"},
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "bad status"
