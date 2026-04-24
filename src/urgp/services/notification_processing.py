"""Notification subscriptions and delivery engine."""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import cast

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from urgp.config import URGPSettings
from urgp.models.enums import BuildStatus, NotificationChannel
from urgp.models.manifest import BuildManifest
from urgp.models.notification import Notification, NotificationSubscription
from urgp.models.product import Product, Release
from urgp.schemas.platform import SubscriptionCreateRequest, SubscriptionListResponse, SubscriptionResponse
from urgp.services.platform_queries import _manifest_load_options


class SubscriptionNotFoundError(LookupError):
    """Raised when a subscription does not exist or is not owned by the caller."""


class NotificationProcessingService:
    """Manage subscriptions and deliver build notifications."""

    def __init__(
        self,
        session_factory_provider: Callable[[], async_sessionmaker[AsyncSession]],
        settings: URGPSettings,
    ) -> None:
        self._session_factory_provider = session_factory_provider
        self._settings = settings

    async def list_subscriptions(self, user_id: str) -> SubscriptionListResponse:
        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            result = await session.scalars(
                select(NotificationSubscription)
                .join(NotificationSubscription.product)
                .outerjoin(NotificationSubscription.release)
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
                .where(
                    NotificationSubscription.user_id == user_id,
                    NotificationSubscription.product_id == product.id,
                    NotificationSubscription.release_id == (release.id if release is not None else None),
                    NotificationSubscription.channel == payload.channel,
                    NotificationSubscription.webhook_url == payload.webhook_url,
                )
                .options(
                    selectinload(NotificationSubscription.product),
                    selectinload(NotificationSubscription.release),
                )
            )
            if existing is not None:
                if not existing.active:
                    existing.active = True
                    await session.commit()
                    await session.refresh(existing)
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
            await session.delete(subscription)
            await session.commit()

    async def process_build_ready(self, build_id: str, product_external_id: str) -> None:
        manifest = await self._wait_for_ready_manifest(build_id, product_external_id)
        if manifest is None:
            return

        # Phase 1: Create pending notification records inside a short-lived transaction.
        session_factory = self._session_factory_provider()
        pending_deliveries: list[tuple[uuid.UUID, NotificationChannel, str, str, str, dict[str, object]]] = []
        async with session_factory() as session:
            subscriptions = await self._load_matching_subscriptions(session, manifest)
            for subscription in subscriptions:
                record = await self._ensure_notification_record(session, manifest, subscription)
                if record is None:
                    continue  # already sent
                subject, body, payload = self._render_notification(manifest, subscription)
                pending_deliveries.append(
                    (record.id, subscription.channel, subscription.user_id, subject, body, payload)
                )
            await session.commit()

        # Phase 2: Deliver notifications OUTSIDE any database transaction.
        delivery_outcomes: list[tuple[uuid.UUID, str, str | None, int]] = []
        for notification_id, channel, user_id, subject, body, payload in pending_deliveries:
            last_error: str | None = None
            delivered = False
            attempts = 0
            for attempt in range(1, self._settings.notification_max_retries + 1):
                attempts = attempt
                try:
                    if channel == NotificationChannel.EMAIL:
                        await self._send_email(user_id, subject, body)
                    else:
                        webhook_url = payload.get("_webhook_url")
                        if isinstance(webhook_url, str):
                            await self._send_webhook(webhook_url, payload)
                        else:
                            msg = "Webhook subscription is missing webhook_url."
                            raise ValueError(msg)
                    delivered = True
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < self._settings.notification_max_retries:
                        delay = self._settings.notification_retry_backoff_seconds * (2 ** (attempt - 1))
                        await asyncio.sleep(delay)

            if delivered:
                delivery_outcomes.append((notification_id, "sent", None, attempts - 1))
            else:
                delivery_outcomes.append((notification_id, "failed", last_error, attempts))

        # Phase 3: Update notification records with delivery outcomes in a new transaction.
        async with session_factory() as session:
            for notification_id, status_value, error_message, retry_count in delivery_outcomes:
                record = await session.get(Notification, notification_id)
                if record is None:
                    continue
                record.status = status_value
                record.error_message = error_message
                record.retry_count = retry_count
                if status_value == "sent":
                    record.sent_at = datetime.now(tz=UTC)
            await session.commit()

    async def _wait_for_ready_manifest(self, build_id: str, product_external_id: str) -> BuildManifest | None:
        deadline = asyncio.get_running_loop().time() + self._settings.notification_wait_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            session_factory = self._session_factory_provider()
            async with session_factory() as session:
                manifest = await session.scalar(
                    select(BuildManifest)
                    .join(BuildManifest.product)
                    .where(
                        BuildManifest.build_id == build_id,
                        Product.external_id == product_external_id,
                    )
                    .options(*_manifest_load_options())
                )
                if manifest is not None and manifest.status in {
                    BuildStatus.COMPLETED,
                    BuildStatus.TESTING,
                    BuildStatus.RELEASED,
                    BuildStatus.DEPRECATED,
                }:
                    return manifest
            await asyncio.sleep(self._settings.notification_poll_interval_seconds)
        msg = (
            f"Build '{build_id}' for product '{product_external_id}' did not reach a "
            "notification-ready state within the timeout window."
        )
        raise RuntimeError(msg)

    async def _load_matching_subscriptions(
        self,
        session: AsyncSession,
        manifest: BuildManifest,
    ) -> list[NotificationSubscription]:
        result = await session.scalars(
            select(NotificationSubscription)
            .join(NotificationSubscription.product)
            .outerjoin(NotificationSubscription.release)
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
        )
        return list(result.all())

    async def _ensure_notification_record(
        self,
        session: AsyncSession,
        manifest: BuildManifest,
        subscription: NotificationSubscription,
    ) -> Notification | None:
        """Create or retrieve a pending notification record. Returns None if already sent."""
        recipient = subscription.webhook_url or subscription.user_id
        existing = await session.scalar(
            select(Notification).where(
                Notification.manifest_id == manifest.id,
                Notification.channel == subscription.channel,
                Notification.recipient == recipient,
            )
        )
        if existing is not None and existing.status == "sent":
            return None

        if existing is not None:
            return existing

        record = Notification(
            manifest_id=manifest.id,
            channel=subscription.channel,
            recipient=recipient,
            status="pending",
            retry_count=0,
        )
        session.add(record)
        await session.flush()
        return record

    def _render_notification(
        self,
        manifest: BuildManifest,
        subscription: NotificationSubscription,
    ) -> tuple[str, str, dict[str, object]]:
        pull_request_count = len(
            {pull_request.id for commit in manifest.commits for pull_request in commit.pull_requests}
        )
        issue_count = len({issue.id for commit in manifest.commits for issue in commit.issues})
        release_value = manifest.release.version if manifest.release is not None else "unassigned"
        portal_link = f"{self._settings.portal_base_url.rstrip('/')}/?build={manifest.build_id}&product={manifest.product.external_id}"

        payload = cast(
            dict[str, object],
            {
                "build_id": manifest.build_id,
                "product": manifest.product.name,
                "product_id": manifest.product.external_id,
                "release": release_value,
                "build_type": manifest.build_type.value,
                "status": manifest.status.value,
                "changes_summary": {
                    "commits": len(manifest.commits),
                    "pull_requests": pull_request_count,
                    "issues": issue_count,
                },
                "portal_url": portal_link,
                "subscription_channel": subscription.channel.value,
                "timestamp": manifest.created_at.isoformat(),
                "_webhook_url": subscription.webhook_url,
            },
        )

        subject = f"[URGP] {manifest.product.name} - {manifest.build_type.value} build {manifest.build_id} ready"
        body = (
            f"Build {manifest.build_id} for {manifest.product.name} is now {manifest.status.value}.\n\n"
            f"Release: {release_value}\n"
            f"Changes: {len(manifest.commits)} commits, {pull_request_count} pull requests, {issue_count} issues\n"
            f"Traceability incomplete: {'yes' if manifest.traceability_incomplete else 'no'}\n"
            f"Portal: {portal_link}\n"
        )
        return subject, body, payload

    async def _send_email(self, recipient: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_email_sync, recipient, subject, body)

    def _send_email_sync(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=10) as smtp:
            if self._settings.smtp_username:
                smtp.login(self._settings.smtp_username, self._settings.smtp_password)
            smtp.send_message(message)

    async def _send_webhook(self, webhook_url: str, payload: dict[str, object]) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()

    def _to_subscription_response(self, subscription: NotificationSubscription) -> SubscriptionResponse:
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


__all__ = [
    "NotificationProcessingService",
    "SubscriptionNotFoundError",
]
