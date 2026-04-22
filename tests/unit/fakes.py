"""Test doubles for Redis-backed gateway services."""

from __future__ import annotations

import json
import time


class FakeRedis:
    """Minimal async Redis double for gateway unit tests."""

    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._string_expiry: dict[str, float] = {}
        self._sorted_sets: dict[str, dict[str, float]] = {}
        self._sorted_set_expiry: dict[str, float] = {}

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        self._purge_expired(key)
        if nx and key in self._strings:
            return False

        self._strings[key] = value
        if ex is not None:
            self._string_expiry[key] = time.time() + ex
        return True

    async def get(self, key: str) -> str | None:
        self._purge_expired(key)
        return self._strings.get(key)

    async def eval(self, _script: str, numkeys: int, *args: object) -> int | list[int]:
        if numkeys != 1:
            msg = "FakeRedis supports exactly one key per eval call"
            raise ValueError(msg)

        key = str(args[0])
        argv = args[1:]

        if len(argv) == 5:
            return self._eval_rate_limit(key, argv)
        if len(argv) == 3:
            return self._eval_complete_reservation(key, argv)
        if len(argv) == 1:
            return self._eval_release_reservation(key, argv)

        msg = f"Unsupported eval signature: {len(argv)} args"
        raise ValueError(msg)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def _purge_expired(self, key: str) -> None:
        now = time.time()
        if key in self._string_expiry and self._string_expiry[key] <= now:
            self._string_expiry.pop(key, None)
            self._strings.pop(key, None)

        if key in self._sorted_set_expiry and self._sorted_set_expiry[key] <= now:
            self._sorted_set_expiry.pop(key, None)
            self._sorted_sets.pop(key, None)

    def _eval_rate_limit(self, key: str, argv: tuple[object, ...]) -> list[int]:
        self._purge_expired(key)

        now = float(argv[0])
        window_start = float(argv[1])
        limit = int(argv[2])
        ttl = int(argv[3])
        member = str(argv[4])

        bucket = self._sorted_sets.setdefault(key, {})
        bucket = {
            existing_member: score
            for existing_member, score in bucket.items()
            if score > window_start
        }
        self._sorted_sets[key] = bucket

        current = len(bucket)
        self._sorted_set_expiry[key] = time.time() + ttl

        if current >= limit:
            return [0, limit, 0]

        bucket[member] = now
        remaining = limit - current - 1
        return [1, limit, remaining]

    def _eval_complete_reservation(self, key: str, argv: tuple[object, ...]) -> int:
        self._purge_expired(key)

        expected_token = str(argv[0])
        replacement = str(argv[1])
        ttl = int(argv[2])

        current = self._strings.get(key)
        if current is None:
            return 0

        decoded = json.loads(current)
        if decoded.get("status") != "pending":
            return 0
        if decoded.get("reservation_token") != expected_token:
            return 0

        self._strings[key] = replacement
        self._string_expiry[key] = time.time() + ttl
        return 1

    def _eval_release_reservation(self, key: str, argv: tuple[object, ...]) -> int:
        self._purge_expired(key)

        expected_token = str(argv[0])
        current = self._strings.get(key)
        if current is None:
            return 0

        decoded = json.loads(current)
        if decoded.get("status") != "pending":
            return 0
        if decoded.get("reservation_token") != expected_token:
            return 0

        self._strings.pop(key, None)
        self._string_expiry.pop(key, None)
        return 1


class FakeResponse:
    """Simple response-like object for dependency tests."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
