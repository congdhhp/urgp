"""P1-8.1: Consolidated security audit test suite.

This module provides a single-file security audit for Phase 1 DoD compliance.
It validates all security controls: authentication, rate limiting, credential
encryption, manifest signatures, input validation, and response headers.

Run with: poetry run pytest tests/unit/test_security_audit.py -v
"""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# Set required env vars before importing the app
os.environ.setdefault("URGP_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("URGP_RABBITMQ_URL", "amqp://test:test@localhost:5672/")
os.environ.setdefault("URGP_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("URGP_JWT_SECRET_KEY", "test-jwt-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("URGP_SIGNING_KEY", "test-signing-key-must-be-at-least-32-characters-long")
os.environ.setdefault("URGP_API_KEY", "test-api-key-for-security-audit")

from pydantic import ValidationError

from urgp.models.enums import ArtifactType, BuildType
from urgp.schemas.ingest import IngestPayload
from urgp.services.secret_config import SecretConfigCodec, SecretConfigError, is_encrypted_value
from urgp.services.signature import ManifestSignatureService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIGNING_KEY = "test-signing-key-must-be-at-least-32-characters-long"
TEST_API_KEY = "test-api-key-for-security-audit"


def _make_app_client() -> AsyncClient:
    """Create an httpx AsyncClient bound to the URGP app."""
    from urgp.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


def _valid_ingest_payload() -> dict:
    """Minimal valid ingest payload for security tests."""
    return {
        "product_id": "sec-audit-product",
        "release": "1.0.0",
        "build_type": "nightly",
        "build_id": "sec-audit-build-001",
        "cli_version": "0.1.0",
        "commit_hashes": [
            {
                "repository": "github.com/test/repo",
                "hash": "a" * 40,
                "branch": "main",
            },
        ],
        "artifacts": [
            {
                "name": "test.zip",
                "type": "generic",
                "storage_uri": "https://example.com/test.zip",
                "sha256": "ab" * 32,
                "size_bytes": 1024,
            },
        ],
        "timestamp": "2026-05-06T12:00:00Z",
    }


# ---------------------------------------------------------------------------
# SEC-01: API Key Authentication
# ---------------------------------------------------------------------------


class TestAPIKeyAuthentication:
    """Verify API key enforcement on protected endpoints."""

    async def test_missing_api_key_returns_401(self) -> None:
        async with _make_app_client() as client:
            response = await client.post("/api/v1/ingest", json=_valid_ingest_payload())
        assert response.status_code == 401

    async def test_invalid_api_key_returns_401(self) -> None:
        async with _make_app_client() as client:
            response = await client.post(
                "/api/v1/ingest",
                json=_valid_ingest_payload(),
                headers={"X-API-Key": "invalid-key-that-does-not-exist"},
            )
        assert response.status_code == 401

    async def test_health_endpoint_does_not_require_auth(self) -> None:
        async with _make_app_client() as client:
            response = await client.get("/health")
        assert response.status_code == 200

    async def test_docs_endpoint_does_not_require_auth(self) -> None:
        async with _make_app_client() as client:
            response = await client.get("/docs")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# SEC-02: Rate Limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Verify rate limiter produces correct headers and enforces limits."""

    async def test_rate_limit_headers_present(self) -> None:
        from tests.unit.fakes import FakeRedis
        from urgp.middleware.rate_limiter import RateLimiter

        limiter = RateLimiter(FakeRedis())
        with patch("urgp.middleware.rate_limiter.time.time", return_value=1000.0):
            result = await limiter.check_rate_limit("sec-audit-key")

        headers = result.as_headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    async def test_rate_limit_enforcement(self) -> None:
        from tests.unit.fakes import FakeRedis
        from urgp.middleware.rate_limiter import RateLimiter

        redis = FakeRedis()
        limiter = RateLimiter(redis)

        # Exhaust limit
        for i in range(5):
            with patch("urgp.middleware.rate_limiter.time.time", return_value=1000.0 + i * 0.1):
                await limiter.check_rate_limit("exhaust-key", is_write=True, write_limit=5)

        # Next request should be rejected
        with patch("urgp.middleware.rate_limiter.time.time", return_value=1005.0):
            result = await limiter.check_rate_limit("exhaust-key", is_write=True, write_limit=5)

        assert result.allowed is False
        assert result.remaining == 0


# ---------------------------------------------------------------------------
# SEC-03: Credential Encryption
# ---------------------------------------------------------------------------


class TestCredentialEncryption:
    """Verify credential encryption at rest."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        codec = SecretConfigCodec(SIGNING_KEY)
        original = "ghp_supersecrettoken123456"

        encrypted = codec.encrypt_value(original)
        assert encrypted != original
        assert is_encrypted_value(encrypted)
        assert codec.decrypt_value(encrypted) == original

    def test_tampered_ciphertext_rejected(self) -> None:
        codec = SecretConfigCodec(SIGNING_KEY)
        encrypted = codec.encrypt_value("secret-data")

        # Tamper with ciphertext
        tampered = encrypted[:-4] + "XXXX"
        with pytest.raises(SecretConfigError):
            codec.decrypt_value(tampered)

    def test_wrong_key_rejected(self) -> None:
        encrypted = SecretConfigCodec(SIGNING_KEY).encrypt_value("secret-data")
        wrong_codec = SecretConfigCodec("different-key-that-is-also-32-characters-long!!")

        with pytest.raises(SecretConfigError):
            wrong_codec.decrypt_value(encrypted)

    def test_nested_config_encryption(self) -> None:
        codec = SecretConfigCodec(SIGNING_KEY)
        config = {
            "provider": "github",
            "credentials": {
                "authentication_token": "ghp_secret_token",
                "email": "public@example.com",
            },
        }

        encrypted = codec.encrypt_config(config)
        # Sensitive fields encrypted
        assert is_encrypted_value(encrypted["credentials"]["authentication_token"])
        # Non-sensitive fields preserved
        assert encrypted["credentials"]["email"] == "public@example.com"
        assert encrypted["provider"] == "github"
        # Roundtrip
        assert codec.decrypt_config(encrypted) == config


# ---------------------------------------------------------------------------
# SEC-04: Manifest Signatures (HMAC-SHA256)
# ---------------------------------------------------------------------------


class TestManifestSignatures:
    """Verify manifest signatures are deterministic and tamper-evident."""

    def _payload(self) -> IngestPayload:
        return IngestPayload(
            product_id="s32-design-studio",
            release="3.6.8-RFP",
            build_type=BuildType.NIGHTLY,
            build_id="260330",
            cli_version="1.0.0",
            commit_hashes=[
                {"repository": "github.com/test/repo", "hash": "a" * 40, "branch": "main"},
            ],
            artifacts=[
                {
                    "name": "artifact.zip",
                    "type": ArtifactType.GENERIC,
                    "storage_uri": "https://artifacts.example.com/artifact.zip",
                    "sha256": "ab" * 32,
                }
            ],
            timestamp=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
        )

    def test_signature_deterministic(self) -> None:
        signer = ManifestSignatureService(SIGNING_KEY)
        payload = self._payload()
        sig1 = signer.sign_payload(payload)
        sig2 = signer.sign_payload(payload)
        assert sig1 == sig2

    def test_signature_changes_on_payload_mutation(self) -> None:
        signer = ManifestSignatureService(SIGNING_KEY)
        payload = self._payload()
        sig_original = signer.sign_payload(payload)

        mutated = payload.model_copy(update={"build_id": "999999"})
        sig_mutated = signer.sign_payload(mutated)

        assert sig_original != sig_mutated

    def test_verify_valid_signature(self) -> None:
        signer = ManifestSignatureService(SIGNING_KEY)
        payload = self._payload()
        sig = signer.sign_payload(payload)
        assert signer.verify_payload(payload, sig) is True

    def test_reject_invalid_signature(self) -> None:
        signer = ManifestSignatureService(SIGNING_KEY)
        payload = self._payload()
        assert signer.verify_payload(payload, "invalid-signature") is False

    def test_ordering_invariant(self) -> None:
        signer = ManifestSignatureService(SIGNING_KEY)
        payload = self._payload()

        reordered_data = deepcopy(payload.model_dump(mode="json"))
        reordered_data["commit_hashes"] = list(reversed(reordered_data["commit_hashes"]))
        reordered_data["artifacts"] = list(reversed(reordered_data["artifacts"]))
        reordered = IngestPayload.model_validate(reordered_data)

        assert signer.sign_payload(payload) == signer.sign_payload(reordered)


# ---------------------------------------------------------------------------
# SEC-05: Input Validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Verify malformed inputs are rejected at the schema layer."""

    def test_empty_payload_rejected(self) -> None:
        """Empty dict missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            IngestPayload.model_validate({})

    def test_missing_required_fields_rejected(self) -> None:
        """Partial payload missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            IngestPayload.model_validate({"product_id": "test"})

    def test_valid_payload_accepted(self) -> None:
        """A well-formed payload validates successfully."""
        payload = IngestPayload.model_validate(_valid_ingest_payload())
        assert payload.product_id == "sec-audit-product"
        assert payload.build_id == "sec-audit-build-001"
        assert len(payload.artifacts) == 1

    def test_invalid_sha256_format_rejected(self) -> None:
        """SHA-256 field must be a valid 64-char hex string."""
        data = _valid_ingest_payload()
        data["artifacts"][0]["sha256"] = "not-a-valid-hex-string"
        with pytest.raises(ValidationError):
            IngestPayload.model_validate(data)

    def test_invalid_commit_hash_rejected(self) -> None:
        """Commit hash must be a 40-char hex string."""
        data = _valid_ingest_payload()
        data["commit_hashes"][0]["hash"] = "short"
        with pytest.raises(ValidationError):
            IngestPayload.model_validate(data)

    async def test_invalid_json_returns_422(self) -> None:
        """Malformed JSON body returns 422."""
        async with _make_app_client() as client:
            response = await client.post(
                "/api/v1/ingest",
                content=b"not-valid-json{{{",
                headers={
                    "X-API-Key": "any-key",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# SEC-06: CORS Configuration
# ---------------------------------------------------------------------------


class TestCORSConfiguration:
    """Verify CORS middleware is configured."""

    async def test_cors_allows_configured_origin(self) -> None:
        async with _make_app_client() as client:
            response = await client.options(
                "/api/v1/ingest",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )
        # CORS preflight should return 200 with allow headers
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
