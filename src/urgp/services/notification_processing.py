"""Notification subscriptions, history, rendering, transport, and orchestration."""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Protocol

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from urgp.config import URGPSettings
from urgp.models.enums import (
    BuildStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from urgp.models.manifest import BuildManifest
from urgp.models.notification import Notification, NotificationSubscription
from urgp.models.product import Product, Release
from urgp.models.traceability import Commit
from urgp.schemas.notifications import NotificationRequest
from urgp.schemas.platform import (
    NotificationHistoryItemResponse,
    NotificationHistoryResponse,
    SubscriptionCreateRequest,
    SubscriptionListResponse,
    SubscriptionResponse,
)

_NOTIFIABLE_STATUS_BY_EVENT: dict[NotificationEventType, BuildStatus] = {
    NotificationEventType.BUILD_COMPLETED: BuildStatus.COMPLETED,
    NotificationEventType.BUILD_RELEASED: BuildStatus.RELEASED,
}


class SubscriptionNotFoundError(LookupError):
    """Raised when a subscription does not exist or is not owned by the caller."""


@dataclass(frozen=True)
class RenderedNotification:
    """Concrete outbound notification ready for transport."""

    channel: NotificationChannel
    destination: str
    subject: str
    body: str
    payload: dict[str, object]


@dataclass(frozen=True)
class DeliveryCandidate:
    """One persisted notification record plus its rendered content."""

    notification_id: uuid.UUID
    rendered: RenderedNotification


@dataclass(frozen=True)
class RetryOutcome:
    """Materialized delivery outcome after all retry attempts complete."""

    status: str
    attempt_count: int
    last_attempt_at: datetime | None
    sent_at: datetime | None
    last_error: str | None


class NotificationTransport(Protocol):
    """Transport contract for one delivery channel."""

    async def send(self, rendered: RenderedNotification) -> None:
        """Send one rendered notification."""


class SubscriptionService:
    """Manage user-owned notification subscriptions."""

    def __init__(self, session_factory_provider: Callable[[], async_sessionmaker[AsyncSession]]) -> None:
        self._session_factory_provider = session_factory_provider

    async def list_subscriptions(self, user_id: str) -> SubscriptionListResponse:
        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            result = await session.scalars(
                select(NotificationSubscription)
                .options(
                    selectinload(NotificationSubscription.product),
                    selectinload(NotificationSubscription.release),
                )
                .where(NotificationSubscription.user_id == user_id)
                .order_by(NotificationSubscription.created_at.desc())
            )
            subscriptions = list(result.all())

        items = [self._to_subscription_response(subscription) for subscription in subscriptions]
        return SubscriptionListResponse(items=items, total=len(items))

    async def create_subscription(
        self,
        user_id: str,
        payload: SubscriptionCreateRequest,
    ) -> SubscriptionResponse:
        if payload.channel == NotificationChannel.EMAIL and "@" not in user_id:
            msg = "Email subscriptions require X-User-Id to be an email address."
            raise ValueError(msg)

        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            product = await session.scalar(select(Product).where(Product.external_id == payload.product_id))
            if product is None:
                msg = f"Product '{payload.product_id}' was not found."
                raise LookupError(msg)

            release: Release | None = None
            if payload.release is not None:
                release = await session.scalar(
                    select(Release).where(
                        Release.product_id == product.id,
                        Release.version == payload.release,
                    )
                )
                if release is None:
                    msg = f"Release '{payload.release}' was not found for product '{payload.product_id}'."
                    raise LookupError(msg)

            existing = await session.scalar(
                select(NotificationSubscription)
                .options(
                    selectinload(NotificationSubscription.product),
                    selectinload(NotificationSubscription.release),
                )
                .where(
                    NotificationSubscription.user_id == user_id,
                    NotificationSubscription.product_id == product.id,
                    NotificationSubscription.release_id == (release.id if release is not None else None),
                    NotificationSubscription.channel == payload.channel,
                    NotificationSubscription.webhook_url == payload.webhook_url,
                )
            )
            if existing is not None:
                if not existing.active:
                    existing.active = True
                    await session.commit()
                    await session.refresh(existing)
                    await session.refresh(existing, attribute_names=["product", "release"])
                return self._to_subscription_response(existing)

            subscription = NotificationSubscription(
                user_id=user_id,
                product_id=product.id,
                release_id=release.id if release is not None else None,
                channel=payload.channel,
                webhook_url=payload.webhook_url,
                active=True,
            )
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)
            await session.refresh(subscription, attribute_names=["product", "release"])

        return self._to_subscription_response(subscription)

    async def delete_subscription(self, user_id: str, subscription_id: uuid.UUID) -> None:
        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            subscription = await session.scalar(
                select(NotificationSubscription).where(
                    NotificationSubscription.id == subscription_id,
                    NotificationSubscription.user_id == user_id,
                )
            )
            if subscription is None:
                msg = f"Subscription '{subscription_id}' was not found."
                raise SubscriptionNotFoundError(msg)
            subscription.active = False
            await session.commit()

    @staticmethod
    def _to_subscription_response(subscription: NotificationSubscription) -> SubscriptionResponse:
        return SubscriptionResponse(
            id=subscription.id,
            user_id=subscription.user_id,
            product_id=subscription.product.external_id,
            product_name=subscription.product.name,
            release=subscription.release.version if subscription.release is not None else None,
            channel=subscription.channel,
            webhook_url=subscription.webhook_url,
            active=subscription.active,
            created_at=subscription.created_at,
        )


class NotificationHistoryService:
    """Read delivery history for the caller's own subscriptions."""

    def __init__(self, session_factory_provider: Callable[[], async_sessionmaker[AsyncSession]]) -> None:
        self._session_factory_provider = session_factory_provider

    async def list_history(
        self,
        user_id: str,
        *,
        build_id: str | None = None,
        product_id: str | None = None,
        channel: NotificationChannel | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> NotificationHistoryResponse:
        normalized_status: str | None = None
        if status is not None:
            normalized_status = NotificationDeliveryStatus(status).value

        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            statement = (
                select(Notification)
                .join(Notification.subscription)
                .join(Notification.manifest)
                .join(BuildManifest.product)
                .outerjoin(BuildManifest.release)
                .where(NotificationSubscription.user_id == user_id)
            )
            if build_id is not None:
                statement = statement.where(BuildManifest.build_id == build_id)
            if product_id is not None:
                statement = statement.where(Product.external_id == product_id)
            if channel is not None:
                statement = statement.where(Notification.channel == channel)
            if normalized_status is not None:
                statement = statement.where(Notification.status == normalized_status)

            query_statement = statement.options(
                selectinload(Notification.subscription),
                selectinload(Notification.manifest).selectinload(BuildManifest.product),
                selectinload(Notification.manifest).selectinload(BuildManifest.release),
            ).order_by(Notification.created_at.desc())
            total = await session.scalar(select(func.count()).select_from(statement.subquery()))
            result = await session.scalars(query_statement.offset(offset).limit(limit))
            records = list(result.all())

        items = [self._to_history_item(record) for record in records]
        return NotificationHistoryResponse(items=items, total=int(total or 0))

    @staticmethod
    def _to_history_item(record: Notification) -> NotificationHistoryItemResponse:
        manifest = record.manifest
        release = manifest.release
        return NotificationHistoryItemResponse(
            id=record.id,
            subscription_id=record.subscription_id,
            manifest_id=manifest.id,
            build_id=manifest.build_id,
            product_id=manifest.product.external_id,
            product_name=manifest.product.name,
            release=release.version if release is not None else None,
            event_type=record.event_type,
            channel=record.channel,
            recipient=record.recipient_snapshot,
            status=NotificationDeliveryStatus(record.status),
            attempt_count=record.attempt_count,
            last_attempt_at=record.last_attempt_at,
            sent_at=record.sent_at,
            last_error=record.last_error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class NotificationRenderer:
    """Render default email and webhook content for one notification event."""

    def __init__(self, settings: URGPSettings) -> None:
        self._portal_base_url = settings.portal_base_url.rstrip("/")

    def render(
        self,
        manifest: BuildManifest,
        subscription: NotificationSubscription,
        request: NotificationRequest,
    ) -> RenderedNotification:
        pull_request_count = len({pull_request.id for commit in manifest.commits for pull_request in commit.pull_requests})
        issue_count = len({issue.id for commit in manifest.commits for issue in commit.issues})
        release_value = manifest.release.version if manifest.release is not None else "unassigned"
        portal_url = f"{self._portal_base_url}/?build={manifest.build_id}&product={manifest.product.external_id}"
        event_label = "Completed" if request.event_type == NotificationEventType.BUILD_COMPLETED else "Released"

        payload = {
            "schema_version": "v1",
            "event_type": request.event_type.value,
            "triggered_at": request.triggered_at.isoformat(),
            "build": {
                "id": manifest.build_id,
                "status": manifest.status.value,
                "type": manifest.build_type.value,
                "product_id": manifest.product.external_id,
                "product_name": manifest.product.name,
                "release_train": release_value,
            },
            "changes_summary": {
                "commits": len(manifest.commits),
                "pull_requests": pull_request_count,
                "issues": issue_count,
            },
            "traceability": {
                "incomplete": manifest.traceability_incomplete,
            },
            "links": {
                "portal": portal_url,
            },
        }
        destination = subscription.webhook_url or subscription.user_id
        subject = f"[URGP] {manifest.product.name} - {event_label} build {manifest.build_id}"
        body = (
            f"{manifest.product.name} build {manifest.build_id} is now {manifest.status.value}.\n\n"
            f"Release train: {release_value}\n"
            f"Build type: {manifest.build_type.value}\n"
            f"Changes: {len(manifest.commits)} commits, {pull_request_count} pull requests, {issue_count} issues\n"
            f"Traceability incomplete: {'yes' if manifest.traceability_incomplete else 'no'}\n"
            f"Portal: {portal_url}\n"
        )
        return RenderedNotification(
            channel=subscription.channel,
            destination=destination,
            subject=subject,
            body=body,
            payload=payload,
        )


class EmailTransport:
    """Send email notifications via SMTP."""

    def __init__(self, settings: URGPSettings) -> None:
        self._settings = settings

    async def send(self, rendered: RenderedNotification) -> None:
        if rendered.channel != NotificationChannel.EMAIL:
            msg = f"EmailTransport cannot send channel '{rendered.channel.value}'."
            raise ValueError(msg)
        await asyncio.to_thread(self._send_sync, rendered)

    def _send_sync(self, rendered: RenderedNotification) -> None:
        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = rendered.destination
        message["Subject"] = rendered.subject
        message.set_content(rendered.body)

        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=10) as smtp:
            if self._settings.smtp_username:
                smtp.login(self._settings.smtp_username, self._settings.smtp_password)
            smtp.send_message(message)


class WebhookTransport:
    """Send webhook notifications over HTTP POST."""

    async def send(self, rendered: RenderedNotification) -> None:
        if rendered.channel != NotificationChannel.WEBHOOK:
            msg = f"WebhookTransport cannot send channel '{rendered.channel.value}'."
            raise ValueError(msg)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(rendered.destination, json=rendered.payload)
            response.raise_for_status()


class RetryPolicy:
    """Retry one delivery using exponential backoff."""

    def __init__(self, *, max_retries: int, base_backoff_seconds: float) -> None:
        self._max_retries = max_retries
        self._base_backoff_seconds = base_backoff_seconds

    async def execute(self, operation: Callable[[], Awaitable[None]]) -> RetryOutcome:
        total_attempts = self._max_retries + 1
        last_attempt_at: datetime | None = None
        last_error: str | None = None

        for attempt in range(1, total_attempts + 1):
            last_attempt_at = datetime.now(tz=UTC)
            try:
                await operation()
            except Exception as exc:
                last_error = str(exc)
                if attempt < total_attempts:
                    delay = self._base_backoff_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                return RetryOutcome(
                    status=NotificationDeliveryStatus.FAILED.value,
                    attempt_count=attempt,
                    last_attempt_at=last_attempt_at,
                    sent_at=None,
                    last_error=last_error,
                )

            return RetryOutcome(
                status=NotificationDeliveryStatus.SENT.value,
                attempt_count=attempt,
                last_attempt_at=last_attempt_at,
                sent_at=datetime.now(tz=UTC),
                last_error=None,
            )

        msg = "RetryPolicy exhausted without producing an outcome."
        raise RuntimeError(msg)


class NotificationOrchestrator:
    """Resolve subscriptions, persist delivery history, and dispatch notifications."""

    def __init__(
        self,
        session_factory_provider: Callable[[], async_sessionmaker[AsyncSession]],
        settings: URGPSettings,
        *,
        renderer: NotificationRenderer | None = None,
        retry_policy: RetryPolicy | None = None,
        transports: dict[NotificationChannel, NotificationTransport] | None = None,
    ) -> None:
        self._session_factory_provider = session_factory_provider
        self._renderer = renderer or NotificationRenderer(settings)
        self._retry_policy = retry_policy or RetryPolicy(
            max_retries=settings.notification_max_retries,
            base_backoff_seconds=settings.notification_retry_backoff_seconds,
        )
        self._transports = transports or {
            NotificationChannel.EMAIL: EmailTransport(settings),
            NotificationChannel.WEBHOOK: WebhookTransport(),
        }

    async def process_request(self, request: NotificationRequest) -> None:
        manifest = await self._load_manifest(request.manifest_id)
        self._validate_request_against_manifest(request, manifest)

        session_factory = self._session_factory_provider()
        pending_deliveries: list[DeliveryCandidate] = []
        async with session_factory() as session:
            subscriptions = await self._load_matching_subscriptions(session, manifest)
            for subscription in subscriptions:
                candidate = await self._prepare_delivery(session, manifest, subscription, request)
                if candidate is not None:
                    pending_deliveries.append(candidate)
            await session.commit()

        outcomes: list[tuple[uuid.UUID, RetryOutcome]] = []
        for candidate in pending_deliveries:
            transport = self._transports.get(candidate.rendered.channel)
            if transport is None:
                msg = f"No transport is registered for channel '{candidate.rendered.channel.value}'."
                raise RuntimeError(msg)
            outcome = await self._retry_policy.execute(lambda: transport.send(candidate.rendered))
            outcomes.append((candidate.notification_id, outcome))

        async with session_factory() as session:
            for notification_id, outcome in outcomes:
                record = await session.get(Notification, notification_id)
                if record is None:
                    continue
                record.status = outcome.status
                record.attempt_count = outcome.attempt_count
                record.last_attempt_at = outcome.last_attempt_at
                record.sent_at = outcome.sent_at
                record.last_error = outcome.last_error
            await session.commit()

    async def _load_manifest(self, manifest_id: uuid.UUID) -> BuildManifest:
        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            manifest = await session.scalar(
                select(BuildManifest)
                .options(*_manifest_load_options())
                .where(BuildManifest.id == manifest_id)
            )
            if manifest is None:
                msg = f"Manifest '{manifest_id}' could not be loaded for notification processing."
                raise RuntimeError(msg)
            return manifest

    @staticmethod
    def _validate_request_against_manifest(request: NotificationRequest, manifest: BuildManifest) -> None:
        if manifest.build_id != request.build_id:
            msg = f"Notification request build '{request.build_id}' does not match manifest '{manifest.build_id}'."
            raise RuntimeError(msg)
        if manifest.product.external_id != request.product_id:
            msg = (
                f"Notification request product '{request.product_id}' does not match "
                f"manifest '{manifest.product.external_id}'."
            )
            raise RuntimeError(msg)

        expected_status = _NOTIFIABLE_STATUS_BY_EVENT[request.event_type]
        if manifest.status != expected_status:
            msg = (
                f"Manifest '{manifest.build_id}' is in status '{manifest.status.value}', "
                f"expected '{expected_status.value}' for event '{request.event_type.value}'."
            )
            raise RuntimeError(msg)

    @staticmethod
    async def _load_matching_subscriptions(
        session: AsyncSession,
        manifest: BuildManifest,
    ) -> list[NotificationSubscription]:
        result = await session.scalars(
            select(NotificationSubscription)
            .options(
                selectinload(NotificationSubscription.product),
                selectinload(NotificationSubscription.release),
            )
            .where(
                NotificationSubscription.active.is_(True),
                NotificationSubscription.product_id == manifest.product_id,
                or_(
                    NotificationSubscription.release_id.is_(None),
                    NotificationSubscription.release_id == manifest.release_id,
                ),
            )
            .order_by(NotificationSubscription.created_at.asc())
        )
        return list(result.all())

    async def _prepare_delivery(
        self,
        session: AsyncSession,
        manifest: BuildManifest,
        subscription: NotificationSubscription,
        request: NotificationRequest,
    ) -> DeliveryCandidate | None:
        rendered = self._renderer.render(manifest, subscription, request)
        existing = await session.scalar(
            select(Notification).where(
                Notification.manifest_id == manifest.id,
                Notification.subscription_id == subscription.id,
                Notification.event_type == request.event_type,
            )
        )
        if existing is not None and existing.status == NotificationDeliveryStatus.SENT.value:
            return None

        if existing is None:
            record = Notification(
                manifest_id=manifest.id,
                subscription_id=subscription.id,
                event_type=request.event_type,
                channel=subscription.channel,
                recipient_snapshot=rendered.destination,
                status=NotificationDeliveryStatus.PENDING.value,
                attempt_count=0,
            )
            session.add(record)
            await session.flush()
        else:
            existing.channel = subscription.channel
            existing.recipient_snapshot = rendered.destination
            existing.status = NotificationDeliveryStatus.PENDING.value
            existing.attempt_count = 0
            existing.last_attempt_at = None
            existing.sent_at = None
            existing.last_error = None
            await session.flush()
            record = existing

        return DeliveryCandidate(notification_id=record.id, rendered=rendered)


def _manifest_load_options() -> tuple[object, ...]:
    return (
        selectinload(BuildManifest.product),
        selectinload(BuildManifest.release),
        selectinload(BuildManifest.artifacts),
        selectinload(BuildManifest.notifications).selectinload(Notification.subscription),
        selectinload(BuildManifest.commits).selectinload(Commit.pull_requests),
        selectinload(BuildManifest.commits).selectinload(Commit.issues),
    )


__all__ = [
    "DeliveryCandidate",
    "EmailTransport",
    "NotificationHistoryService",
    "NotificationOrchestrator",
    "NotificationRenderer",
    "NotificationTransport",
    "RenderedNotification",
    "RetryOutcome",
    "RetryPolicy",
    "SubscriptionNotFoundError",
    "SubscriptionService",
    "WebhookTransport",
]
