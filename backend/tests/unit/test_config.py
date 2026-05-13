"""P1-1.T1: Configuration validation tests.

Tests:
- Valid config loads correctly
- Invalid config fails fast with clear error
- SecretStr masking works
- Environment validation (production safety)
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from urgp.config import URGPSettings

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _make_env(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Create a complete set of valid environment variables."""
    base: dict[str, str] = {
        "URGP_DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        "URGP_RABBITMQ_URL": "amqp://user:pass@localhost:5672/",
        "URGP_REDIS_URL": "redis://localhost:6379/0",
        "URGP_JWT_SECRET_KEY": "test-jwt-secret-key-must-be-at-least-32-characters-long",
        "URGP_SIGNING_KEY": "test-signing-key-must-be-at-least-32-characters-long",
        "URGP_ENVIRONMENT": "development",
    }
    if overrides:
        base.update(overrides)
    return base


# ─────────────────────────────────────────────
# Test: Valid Configuration
# ─────────────────────────────────────────────


class TestValidConfig:
    """Tests for successful configuration loading."""

    def test_valid_config_loads(self) -> None:
        """Valid environment variables produce a valid URGPSettings."""
        env = _make_env()
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        assert settings.environment == "development"
        assert settings.database_pool_size == 10
        assert settings.rate_limit_read == 100
        assert settings.rate_limit_write == 20
        assert settings.log_level == "INFO"

    def test_default_values(self) -> None:
        """Default values are applied when not specified."""
        env = _make_env()
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        assert settings.debug is False
        assert settings.smtp_host == "localhost"
        assert settings.smtp_port == 1025
        assert settings.api_prefix == "/api/v1"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.workers == 1

    def test_override_defaults(self) -> None:
        """Environment variables override default values."""
        env = _make_env(
            {
                "URGP_LOG_LEVEL": "DEBUG",
                "URGP_DEBUG": "true",
                "URGP_SMTP_PORT": "587",
                "URGP_RATE_LIMIT_READ": "200",
            }
        )
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        assert settings.log_level == "DEBUG"
        assert settings.debug is True
        assert settings.smtp_port == 587
        assert settings.rate_limit_read == 200

    def test_cors_origins_list(self) -> None:
        """CORS origins can be set as a JSON array string."""
        env = _make_env(
            {
                "URGP_CORS_ORIGINS": '["http://localhost:3000","http://example.com"]',
            }
        )
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        assert len(settings.cors_origins) == 2
        assert "http://localhost:3000" in settings.cors_origins


# ─────────────────────────────────────────────
# Test: Invalid Configuration (Fail-Fast)
# ─────────────────────────────────────────────


class TestInvalidConfig:
    """Tests for configuration validation failures."""

    def test_missing_required_database_url(self) -> None:
        """Missing DATABASE_URL raises ValidationError."""
        env = _make_env()
        del env["URGP_DATABASE_URL"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                URGPSettings()  # type: ignore[call-arg]
        # Ensure the error mentions the field
        assert "database_url" in str(exc_info.value).lower()

    def test_missing_required_rabbitmq_url(self) -> None:
        """Missing RABBITMQ_URL raises ValidationError."""
        env = _make_env()
        del env["URGP_RABBITMQ_URL"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError):
                URGPSettings()  # type: ignore[call-arg]

    def test_missing_required_jwt_secret(self) -> None:
        """Missing JWT_SECRET_KEY raises ValidationError."""
        env = _make_env()
        del env["URGP_JWT_SECRET_KEY"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError):
                URGPSettings()  # type: ignore[call-arg]

    def test_jwt_secret_too_short(self) -> None:
        """JWT_SECRET_KEY shorter than 32 chars raises ValidationError."""
        env = _make_env({"URGP_JWT_SECRET_KEY": "too-short"})
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                URGPSettings()  # type: ignore[call-arg]
        assert "jwt_secret_key" in str(exc_info.value).lower()

    def test_invalid_log_level(self) -> None:
        """Invalid LOG_LEVEL raises ValidationError with clear message."""
        env = _make_env({"URGP_LOG_LEVEL": "VERBOSE"})
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                URGPSettings()  # type: ignore[call-arg]
        assert "VERBOSE" in str(exc_info.value)

    def test_invalid_environment(self) -> None:
        """Invalid ENVIRONMENT raises ValidationError."""
        env = _make_env({"URGP_ENVIRONMENT": "testing"})
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                URGPSettings()  # type: ignore[call-arg]
        assert "testing" in str(exc_info.value)

    def test_production_with_debug_fails(self) -> None:
        """Debug mode in production raises ValidationError."""
        env = _make_env(
            {
                "URGP_ENVIRONMENT": "production",
                "URGP_DEBUG": "true",
            }
        )
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                URGPSettings()  # type: ignore[call-arg]
        assert "production" in str(exc_info.value).lower()

    def test_invalid_pool_size(self) -> None:
        """Pool size 0 or negative raises ValidationError."""
        env = _make_env({"URGP_DATABASE_POOL_SIZE": "0"})
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValidationError):
                URGPSettings()  # type: ignore[call-arg]

    def test_invalid_port(self) -> None:
        """Port outside valid range raises ValidationError."""
        env = _make_env({"URGP_PORT": "99999"})
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValidationError):
                URGPSettings()  # type: ignore[call-arg]


# ─────────────────────────────────────────────
# Test: Sensitive Value Masking
# ─────────────────────────────────────────────


class TestMasking:
    """Tests for sensitive value masking in logs."""

    def test_masked_dict_hides_secrets(self) -> None:
        """masked_dict() replaces sensitive values with ***MASKED***."""
        env = _make_env({"URGP_API_KEYS": '["test-api-key"]'})
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        masked = settings.masked_dict()
        assert masked["api_keys"] == "***MASKED***"
        assert masked["jwt_secret_key"] == "***MASKED***"
        assert masked["signing_key"] == "***MASKED***"

    def test_masked_dict_preserves_non_sensitive(self) -> None:
        """masked_dict() keeps non-sensitive values intact."""
        env = _make_env()
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        masked = settings.masked_dict()
        assert masked["environment"] == "development"
        assert masked["log_level"] == "INFO"
        assert masked["smtp_host"] == "localhost"

    def test_database_url_str_property(self) -> None:
        """database_url_str returns a string representation."""
        env = _make_env()
        with patch.dict(os.environ, env, clear=False):
            settings = URGPSettings()  # type: ignore[call-arg]

        url = settings.database_url_str
        assert isinstance(url, str)
        assert "postgresql" in url
