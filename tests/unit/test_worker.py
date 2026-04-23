"""Unit tests for the hydration worker consumer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from urgp.services.build_processing import PersistedBuildResult
from urgp.worker.hydration_worker import HydrationWorker


class _ProcessContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.requeue: bool | None = None

    def process(self, *, requeue: bool = False) -> _ProcessContext:
        self.requeue = requeue
        return _ProcessContext()


def _valid_payload_bytes() -> bytes:
    timestamp = datetime.now(tz=UTC).isoformat()
    return (
        "{"
        '"product_id":"s32-design-studio",'
        '"release":"3.6.8-RFP",'
        '"build_type":"nightly",'
        '"build_id":"260330",'
        '"cli_version":"1.0.0",'
        '"commit_hashes":[{"repository":"bitbucket.org/nxp/s32k3_dev","hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","branch":"main"}],'
        '"artifacts":[{"name":"s32-ide.zip","type":"eclipse_p2","storage_uri":"https://artifacts.internal/s32-ide.zip","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],'
        f'"timestamp":"{timestamp}"'
        "}"
    ).encode()


class TestHydrationWorker:
    """The worker must deserialize and delegate messages predictably."""

    @pytest.mark.asyncio
    async def test_handle_message_processes_valid_payload(self) -> None:
        processor = MagicMock()
        processor.process = AsyncMock(
            return_value=PersistedBuildResult(
                manifest_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                release_id=uuid.uuid4(),
                signature="abc123",
                created=True,
                traceability_incomplete=True,
            )
        )
        worker = HydrationWorker(MagicMock(), processor)
        message = _FakeMessage(_valid_payload_bytes())

        await worker._handle_message(message)

        processor.process.assert_awaited_once()
        payload = processor.process.await_args.args[0]
        assert payload.build_id == "260330"
        assert payload.product_id == "s32-design-studio"
        assert message.requeue is False

    @pytest.mark.asyncio
    async def test_handle_message_rejects_invalid_payload(self) -> None:
        processor = MagicMock()
        processor.process = AsyncMock()
        worker = HydrationWorker(MagicMock(), processor)
        message = _FakeMessage(b'{"product_id":"broken"}')

        with pytest.raises(ValidationError):
            await worker._handle_message(message)

        processor.process.assert_not_awaited()
        assert message.requeue is False
