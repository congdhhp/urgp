"""Idempotency service — Redis-backed duplicate detection with reservations.

The gateway uses a two-phase Redis record:
1. Reserve the build with a short-lived ``pending`` marker before publish.
2. Mark it ``completed`` only after RabbitMQ accepts the event.

This avoids permanent event loss on ordinary publish failures while still
blocking duplicate retries once a publish has completed successfully.

Reference: docs/07-implementation-plan.md § P1-3.3
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

RedisType = aioredis.Redis

_KEY_PREFIX = "idempotency"
_STATUS_PENDING = "pending"
_STATUS_COMPLETED = "completed"

_COMPLETE_RESERVATION_SCRIPT = """
local key = KEYS[1]
local expected_token = ARGV[1]
local replacement = ARGV[2]
local ttl = tonumber(ARGV[3])

local current = redis.call("GET", key)
if not current then
  return 0
end

local decoded = cjson.decode(current)
if decoded["status"] ~= "pending" then
  return 0
end

if decoded["reservation_token"] ~= expected_token then
  return 0
end

redis.call("SET", key, replacement, "EX", ttl)
return 1
"""

_RELEASE_RESERVATION_SCRIPT = """
local key = KEYS[1]
local expected_token = ARGV[1]

local current = redis.call("GET", key)
if not current then
  return 0
end

local decoded = cjson.decode(current)
if decoded["status"] ~= "pending" then
  return 0
end

if decoded["reservation_token"] ~= expected_token then
  return 0
end

redis.call("DEL", key)
return 1
"""

IdempotencyStatus = Literal["started", "duplicate", "in_progress"]


@dataclass(frozen=True)
class IdempotencyReservation:
    """Result of starting idempotent processing for a build event."""

    status: IdempotencyStatus
    reservation_token: str | None = None
    original_timestamp: datetime | None = None
    pending_since: datetime | None = None


@dataclass(frozen=True)
class _StoredRecord:
    """Internal representation of an idempotency record."""

    status: str
    reservation_token: str | None = None
    timestamp: datetime | None = None


def _make_key(product_id: str, build_id: str) -> str:
    return f"{_KEY_PREFIX}:{product_id}:{build_id}"


def _serialize_pending_record(reservation_token: str, timestamp: datetime) -> str:
    return json.dumps(
        {
            "status": _STATUS_PENDING,
            "reservation_token": reservation_token,
            "timestamp": timestamp.isoformat(),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _serialize_completed_record(timestamp: datetime) -> str:
    return json.dumps(
        {
            "status": _STATUS_COMPLETED,
            "timestamp": timestamp.isoformat(),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _decode_redis_value(value: bytes | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _parse_timestamp(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str):
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _parse_record(value: bytes | str | None) -> _StoredRecord | None:
    decoded = _decode_redis_value(value)
    if not decoded:
        return None

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        logger.warning("Could not decode idempotency record payload")
        return None

    status = payload.get("status")
    if status not in {_STATUS_PENDING, _STATUS_COMPLETED}:
        logger.warning("Unknown idempotency status: %s", status)
        return None

    return _StoredRecord(
        status=status,
        reservation_token=payload.get("reservation_token"),
        timestamp=_parse_timestamp(payload.get("timestamp")),
    )


class IdempotencyService:
    """Redis-backed idempotency check for build ingestion."""

    def __init__(
        self,
        redis_client: RedisType,
        *,
        completed_ttl_seconds: int,
        pending_ttl_seconds: int,
    ) -> None:
        self._redis = redis_client
        self._completed_ttl_seconds = completed_ttl_seconds
        self._pending_ttl_seconds = pending_ttl_seconds

    async def _eval_script(self, script: str, *args: str) -> Any:
        eval_fn = cast(Any, self._redis.eval)
        return await eval_fn(script, 1, *args)

    async def begin_processing(self, build_id: str, product_id: str) -> IdempotencyReservation:
        """Reserve the build for processing or report its current state."""
        key = _make_key(product_id, build_id)
        now = datetime.now(tz=UTC)
        reservation_token = uuid.uuid4().hex
        pending_record = _serialize_pending_record(reservation_token, now)

        was_reserved = await self._redis.set(
            key,
            pending_record,
            nx=True,
            ex=self._pending_ttl_seconds,
        )
        if was_reserved:
            logger.info(
                "Idempotency: reserved build event [product=%s, build=%s]",
                product_id,
                build_id,
            )
            return IdempotencyReservation(
                status="started",
                reservation_token=reservation_token,
                pending_since=now,
            )

        existing_record = _parse_record(await self._redis.get(key))
        if existing_record is None:
            logger.warning(
                "Idempotency record unreadable; retrying reservation [product=%s, build=%s]",
                product_id,
                build_id,
            )
            was_reserved = await self._redis.set(
                key,
                pending_record,
                nx=True,
                ex=self._pending_ttl_seconds,
            )
            if was_reserved:
                return IdempotencyReservation(
                    status="started",
                    reservation_token=reservation_token,
                    pending_since=now,
                )

            existing_record = _parse_record(await self._redis.get(key))

        if existing_record and existing_record.status == _STATUS_COMPLETED:
            logger.info(
                "Idempotency: duplicate build event [product=%s, build=%s]",
                product_id,
                build_id,
            )
            return IdempotencyReservation(
                status="duplicate",
                original_timestamp=existing_record.timestamp,
            )

        logger.info(
            "Idempotency: build event already in progress [product=%s, build=%s]",
            product_id,
            build_id,
        )
        return IdempotencyReservation(
            status="in_progress",
            pending_since=existing_record.timestamp if existing_record else now,
        )

    async def mark_completed(
        self,
        build_id: str,
        product_id: str,
        reservation_token: str,
        *,
        ingestion_timestamp: datetime,
    ) -> bool:
        """Transition a pending reservation to a completed idempotency record."""
        key = _make_key(product_id, build_id)
        completed_record = _serialize_completed_record(ingestion_timestamp)

        result = await self._eval_script(
            _COMPLETE_RESERVATION_SCRIPT,
            key,
            reservation_token,
            completed_record,
            str(self._completed_ttl_seconds),
        )
        return bool(int(result))

    async def release_reservation(self, build_id: str, product_id: str, reservation_token: str) -> bool:
        """Release a pending reservation after a failed publish attempt."""
        key = _make_key(product_id, build_id)
        result = await self._eval_script(
            _RELEASE_RESERVATION_SCRIPT,
            key,
            reservation_token,
        )
        return bool(int(result))

    async def get_status(self, build_id: str, product_id: str) -> datetime | None:
        """Return the original completion timestamp for a processed build."""
        key = _make_key(product_id, build_id)
        record = _parse_record(await self._redis.get(key))
        if record and record.status == _STATUS_COMPLETED:
            return record.timestamp
        return None
